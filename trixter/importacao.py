"""Tela de importação de extrato e comprovante em PDF."""
import hashlib
import re
import time
import uuid
from contextlib import closing
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from pypdf.errors import EmptyFileError, FileNotDecryptedError, PyPdfError

LIMITE_BYTES = 2 * 1024 * 1024
LIMITE_PAGINAS = 15
LIMITE_CARACTERES = 200_000
LIMITE_MOVIMENTACOES = 300
LIMITE_SEGUNDOS = 3
_CHAVE_TEXTO = "pdf_texto_sessao"

MSG_TAMANHO = "O PDF passa de 2 MB. Escolha um arquivo menor."
MSG_VAZIO = "O PDF está vazio."
MSG_INVALIDO = "O arquivo não é um PDF válido."
MSG_PAGINAS = "O PDF tem mais de 15 páginas."
MSG_TEXTO = "O texto do PDF passa de 200 mil caracteres."
MSG_TEMPO = "A leitura do PDF demorou demais."
MSG_SENHA = "Este PDF é protegido por senha e não pode ser importado."
MSG_LEITURA = "Não foi possível ler este PDF."
MSG_MOVIMENTACOES = "O extrato tem mais de 300 movimentações."


class PdfRecusado(Exception):
    def __init__(self, mensagem):
        super().__init__(mensagem)
        self.mensagem = mensagem


def _conteudo_pdf(arquivo):
    """Lê no máximo 2 MiB e confere a assinatura antes do PdfReader."""
    if isinstance(arquivo, (bytes, bytearray)):
        dados = bytes(arquivo)
    else:
        tamanho = getattr(arquivo, "size", None)
        if tamanho is not None and int(tamanho) > LIMITE_BYTES:
            raise PdfRecusado(MSG_TAMANHO)
        if hasattr(arquivo, "seek"):
            arquivo.seek(0)
        leitura = arquivo.read(LIMITE_BYTES + 1)
        dados = leitura if isinstance(leitura, (bytes, bytearray)) else bytes(leitura)
    if not dados:
        raise PdfRecusado(MSG_VAZIO)
    if len(dados) > LIMITE_BYTES:
        raise PdfRecusado(MSG_TAMANHO)
    if b"%PDF-" not in dados[:1024]:
        raise PdfRecusado(MSG_INVALIDO)
    return dados


def extrair_texto_pdf(dados, PdfReader, agora=time.monotonic):
    """Extrai o texto de um PDF que já passou do limite de tamanho.

    O prazo de 3 segundos é medido entre as páginas, antes de cada
    extract_text. Essa medição não interrompe uma chamada individual
    de extract_text: a página em leitura segue até o fim.
    """
    leitor = None
    try:
        leitor = PdfReader(BytesIO(dados))
        paginas = leitor.pages
        if len(paginas) > LIMITE_PAGINAS:
            raise PdfRecusado(MSG_PAGINAS)
        trechos = []
        total = 0
        inicio = agora()
        for pagina in paginas:
            if agora() - inicio > LIMITE_SEGUNDOS:
                raise PdfRecusado(MSG_TEMPO)
            texto = pagina.extract_text() or ""
            if not isinstance(texto, str):
                texto = str(texto)
            separador = 1 if trechos else 0
            if total + separador + len(texto) > LIMITE_CARACTERES:
                raise PdfRecusado(MSG_TEXTO)
            trechos.append(texto)
            total += separador + len(texto)
        return "\n".join(trechos)
    except PdfRecusado:
        raise
    except FileNotDecryptedError:
        raise PdfRecusado(MSG_SENHA) from None
    except EmptyFileError:
        raise PdfRecusado(MSG_VAZIO) from None
    except PyPdfError:
        raise PdfRecusado(MSG_LEITURA) from None
    finally:
        fechar = getattr(leitor, "close", None)
        if callable(fechar):
            fechar()


def texto_pdf_da_sessao(arquivo, usuario_id, PdfReader, agora=time.monotonic, sessao=None):
    """Reaproveita o texto na sessão de quem está logado.

    A identidade é o id do usuário junto com o SHA-256 do conteúdo.
    Outro usuário, ou outro arquivo, não recebe esse texto. A sessão
    guarda um único resultado e o substitui quando o conteúdo muda.
    """
    if sessao is None:
        sessao = st.session_state
    dados = _conteudo_pdf(arquivo)
    conteudo = hashlib.sha256(dados).hexdigest()
    usuario = str(usuario_id)
    guardado = sessao.get(_CHAVE_TEXTO)
    if (
        isinstance(guardado, dict)
        and guardado.get("usuario") == usuario
        and guardado.get("conteudo") == conteudo
        and isinstance(guardado.get("texto"), str)
    ):
        return guardado["texto"]
    texto = extrair_texto_pdf(dados, PdfReader, agora=agora)
    sessao[_CHAVE_TEXTO] = {
        "usuario": usuario,
        "conteudo": conteudo,
        "texto": texto,
    }
    return texto


def exibir_importacao_pdf(conectar_banco, listar_categorias, formatar_moeda, PdfReader, tipo_pessoa, termo_gasto):

    st.header("Importar Extrato PDF")

    st.write(
     "Importe seu extrato e revise as movimentações antes de adicioná-las à sua conta."
    )

    arquivo_pdf = st.file_uploader(
     "Selecione um arquivo PDF",
     type=["pdf"],
     key="arquivo_pdf"
    )

    if arquivo_pdf is not None:

       try:
          texto_pdf = texto_pdf_da_sessao(
             arquivo_pdf,
             st.session_state.usuario_atual["id_usuario"],
             PdfReader,
          )
       except PdfRecusado as recusa:
          st.error(recusa.mensagem)
          return

       tipo_pdf = st.selectbox(
          "Qual tipo de PDF deseja importar?",
          [
             "Comprovante individual",
             "Extrato bancário",
          ],
             key="tipo_pdf_importacao"
       )

       if tipo_pdf == "Comprovante individual":

          padrao_valor = r"Valor original:\s*R\$\s*([\d.,]+)"
          valor_encontrado = re.search(padrao_valor, texto_pdf)
          if valor_encontrado:
             valor_texto = valor_encontrado.group(1)
             valor_numerico = float(valor_texto.replace(".", "").replace(",", "."))
             st.write(f"Valor encontrado:", valor_texto)
          else:
             st.warning("Valor não encontrado no PDF.")


          padrao_data = r"Realizado\s+em\s+(\d{2}/\d{2}/\d{4})"
          data_encontrada = re.search(padrao_data, texto_pdf)



          if data_encontrada:
             data_texto = data_encontrada.group(1)

             data_transacao = datetime.strptime(
                               data_texto,
                               "%d/%m/%Y"
                            )
             st.write(f"Data encontrada:", data_texto)
          else:
             st.warning("Data não encontrada no PDF.")



          padrao_destinatario = r"Para\s+([^\n]+)"
          destinatario_encontrado = re.search(
             padrao_destinatario,
             texto_pdf
          )

          if destinatario_encontrado:
             destinatario_texto = destinatario_encontrado.group(1).strip()
             st.write(f"Destinatário  encontrado:", destinatario_texto)
          else:
             st.warning("Destinatário não encontrado no PDF.")


          if valor_encontrado and data_encontrada and destinatario_encontrado:

             tipo_importacao = st.selectbox(
                "Tipo da movimentação:",
                ["Receita", termo_gasto],
                key= "tipo_importacao"
             )
             tipo_importacao_interno = tipo_importacao

             if tipo_importacao == "Despesa":
               tipo_importacao_interno = "Gasto"


             with closing(conectar_banco()) as conexao_categorias:
                 with closing(conexao_categorias.cursor()) as cursor_categorias:
                     categorias_importacao = listar_categorias(
                         cursor_categorias,
                         st.session_state.usuario_atual["id_usuario"],
                         tipo_pessoa,
                         tipo_importacao_interno,
                     )

             categoria_importacao = st.selectbox(
                "Categoria da transação:",
                categorias_importacao,
                key="categoria_importacao_pdf"
             )

             classificacao_importacao = st.selectbox(
                "Classificação da transação:",
                ["Não classificado", "Fixo", "Variável"],
                key="classificacao_importacao_pdf",
                help="Escolha a classificação deste lançamento. Ela não é deduzida pela categoria."
             )

             st.subheader("Prévia da Transação")

             st.write(f"Data: {data_transacao.strftime("%d/%m/%Y")}")
             st.write(f"Descrição: {destinatario_texto}")
             st.write(f"Valor: {formatar_moeda(valor_numerico)}")
             st.write(f"Tipo: {tipo_importacao}")
             st.write(f"Categoria: {categoria_importacao}")
             st.write(f"Classificação: {classificacao_importacao}")

             btn_confirmar_importacao = st.button(
                "Confirmar Importação",
                key="btn_confirmar_importacao_pdf",
                type="primary"
             )

             if st.session_state.get("importacao_pdf_sucesso"):
                st.success(st.session_state.importacao_pdf_sucesso)

             if btn_confirmar_importacao:

                if valor_numerico <= 0:
                   st.error("O valor da transação deve ser maior que zero.")
                   st.stop()

                elif not categoria_importacao:
                   st.error("Selecione uma categoria para a transação.")
                   st.stop()

                else:
                 nova_transacao = {
                   "id_transacao": str(uuid.uuid4()),
                   "id_usuario": st.session_state.usuario_atual["id_usuario"],
                   "tipo": tipo_importacao_interno,
                   "data": data_transacao,
                   "categoria": categoria_importacao,
                   "valor": valor_numerico,
                   "descricao": destinatario_texto,
                   "classificacao": None if classificacao_importacao == "Não classificado" else classificacao_importacao
                }

                 conexao = conectar_banco()
                 cursor = conexao.cursor()

                if tipo_importacao_interno == "Receita":

                   cursor.execute(
                      """
                      INSERT INTO dbo.receitas(
                         id_transacao,
                         id_usuario,
                         categoria,
                         valor,
                         data,
                         descricao,
                         classificacao
                         )
                         VALUES (?,?,?,?,?,?,?)
                         """,
                         nova_transacao["id_transacao"],
                         nova_transacao["id_usuario"],
                         nova_transacao["categoria"],
                         nova_transacao["valor"],
                         nova_transacao["data"],
                         nova_transacao["descricao"],
                         nova_transacao["classificacao"]
                   )
                else:
                   cursor.execute(
                      """
                      INSERT INTO dbo.gastos(
                         id_transacao,
                         id_usuario,
                         categoria,
                         valor,
                         data,
                         descricao,
                         classificacao
                         )
                         VALUES (?,?,?,?,?,?,?)
                         """,
                         nova_transacao["id_transacao"],
                         nova_transacao["id_usuario"],
                         nova_transacao["categoria"],
                         nova_transacao["valor"],
                         nova_transacao["data"],
                         nova_transacao["descricao"],
                         nova_transacao["classificacao"]
                   )
                conexao.commit()
                cursor.close()
                conexao.close()



                sufixo_importacao = (
                   "importada"
                   if tipo_importacao_interno == "Receita"
                   else "importado" if termo_gasto == "Gasto"
                   else "importada"

                )

                st.session_state.importacao_pdf_sucesso =(
                   f"{tipo_importacao} {sufixo_importacao} com sucesso!"
                )
                st.rerun()

          else:
           st.error(
             "Não foi possível identificar todos os dados do comprovante."
             )


       elif tipo_pdf == "Extrato bancário":

         linhas_pdf = texto_pdf.splitlines()

         st.write("Linhas extraídas do PDF:")
         st.write(linhas_pdf)

         movimentacoes_encontradas = []

         for linha in linhas_pdf:

            data_encontrada = re.search(
               r"(\d{2}/\d{2}/\d{4})", linha
            )

            valor_encontrado = re.search(
               r"(-?[\d\.]+,\d{2})$", linha
            )


            if data_encontrada and valor_encontrado:
               st.write("Movimentação encontrada:",linha)
               if "SALDO DO DIA" in linha.upper():
                  continue
               data_texto = data_encontrada.group(1)
               valor_texto = valor_encontrado.group(1)

               valor_numerico = float(valor_texto.replace(".", "").replace(",", "."))

               descricao_movimentacao = (
                linha
                .replace(data_texto, "")
                .replace(valor_texto,"")
                )

               if valor_numerico < 0:
                  tipo_movimentacao = termo_gasto
               else:
                  tipo_movimentacao = "Receita"

               movimentacoes_encontradas.append(
                  {
                "data": data_texto,
                "descricao":descricao_movimentacao,
                "valor": valor_numerico,
                "tipo": tipo_movimentacao,
                "linha": linha
                  }
                )
               if len(movimentacoes_encontradas) > LIMITE_MOVIMENTACOES:
                  st.error(MSG_MOVIMENTACOES)
                  return

         if movimentacoes_encontradas:
            df_movimentacoes = pd.DataFrame(movimentacoes_encontradas)

            df_revisao = df_movimentacoes[
               ["data", "descricao", "valor", "tipo"]
            ].copy()
            df_revisao["importar"] = True
            df_revisao["categoria"] = None
            df_revisao["classificacao"] = "Não classificado"
            df_revisao= df_revisao[
               ["importar","data","descricao","valor","tipo","categoria","classificacao"]
            ]
            df_gastos = df_revisao[
               df_revisao["tipo"] == termo_gasto
            ].copy()
            df_receitas = df_revisao[
               df_revisao["tipo"] == "Receita"
            ].copy()

            with closing(conectar_banco()) as conexao_categorias:
                with closing(conexao_categorias.cursor()) as cursor_categorias:
                    categorias_gasto = listar_categorias(
                        cursor_categorias,
                        st.session_state.usuario_atual["id_usuario"],
                        tipo_pessoa,
                        termo_gasto,
                    )
                    categorias_receita = listar_categorias(
                        cursor_categorias,
                        st.session_state.usuario_atual["id_usuario"],
                        tipo_pessoa,
                        "Receita",
                    )

            dfs_editados = []

            if not df_gastos.empty:
               st.subheader(f"Revisar {termo_gasto}s")
               df_gastos_editado = st.data_editor(
                  df_gastos,
                  use_container_width=True,
                  hide_index=True,
                  column_config = {
                     "classificacao": st.column_config.SelectboxColumn(
                        "Classificação", options=["Não classificado", "Fixo", "Variável"], required=True
                     ),
                     "importar": st.column_config.CheckboxColumn(
                     "Importar"
                  ),
                      "categoria": st.column_config.SelectboxColumn(
                     "Categoria",
                     options=categorias_gasto,
                     required=True
                  )
                },
                   disabled={"tipo"}
             )
               dfs_editados.append(df_gastos_editado)

            if not df_receitas.empty:
                st.subheader("Revisar Receitas")
                df_receitas_editado = st.data_editor(
                   df_receitas,
                   use_container_width=True,
                   hide_index=True,
                   column_config = {
                      "classificacao": st.column_config.SelectboxColumn(
                         "Classificação", options=["Não classificado", "Fixo", "Variável"], required=True
                      ),
                      "importar": st.column_config.CheckboxColumn(
                      "Importar"
                   ),
                   "categoria": st.column_config.SelectboxColumn(
                      "Categoria",
                      options=categorias_receita,
                      required=True
                   )
                },
                   disabled={"tipo"}
             )
                dfs_editados.append(df_receitas_editado)



            df_editado = pd.concat(
                dfs_editados,
                ignore_index=True
             )


            df_para_importar = df_editado[
               df_editado["importar"]
            ].copy()

            st.write(
               f"{len(df_para_importar)} movimentações selecionadas para importação."
            )

            categorias_pendentes = df_para_importar[
               df_para_importar["categoria"].isna()
            ]

            if not categorias_pendentes.empty:
               st.warning(
                  "Selecione uma categoria para todas as movimentações que serão importadas."
               )
            else:
               st.success(
                  "Todas as movimentações selecionadas possuem categoria."
               )

               btn_confirmar_importacao = st.button(
                "Confirmar Importação",
                key="btn_confirmar_importacao_extrato",
                type="primary"
               )

               if st.session_state.get("importacao_sucesso") is not None:
                  st.success(
                     f"{st.session_state.importacao_sucesso} movimentações importadas com sucesso!"
                   )


               if btn_confirmar_importacao:

                  quantidade_importada = 0

                  for _, movimentacao in df_para_importar.iterrows():

                     data_importada = movimentacao["data"]
                     descricao_importada = movimentacao["descricao"]
                     valor_importado = movimentacao["valor"]
                     tipo_importado = movimentacao["tipo"]
                     categoria_importada = movimentacao["categoria"]
                     classificacao_importada = movimentacao["classificacao"]
                     if pd.isna(classificacao_importada) or classificacao_importada == "Não classificado":
                        classificacao_importada = None

                     valor_importado = abs(valor_importado)

                     transacao_duplicada = False



                     conexao = conectar_banco()
                     cursor = conexao.cursor()

                     if tipo_importado == termo_gasto:


                        cursor.execute(
                           """
                           SELECT id_transacao
                           FROM dbo.gastos
                           WHERE id_usuario = ?
                           AND data = ?
                           AND descricao = ?
                           AND valor = ?
                           """,
                           st.session_state.usuario_atual["id_usuario"],
                           data_importada,
                           descricao_importada,
                           valor_importado
                        )

                        transacao_duplicada = cursor.fetchone() is not None
                        cursor.close()
                        conexao.close()

                     else:

                        cursor.execute(
                           """
                           SELECT id_transacao
                           FROM dbo.receitas
                           WHERE id_usuario = ?
                           AND data = ?
                           AND descricao = ?
                           AND valor = ?
                           """,
                           st.session_state.usuario_atual["id_usuario"],
                           data_importada,
                           descricao_importada,
                           valor_importado
                        )

                        transacao_duplicada = cursor.fetchone() is not None
                        cursor.close()
                        conexao.close()


                     if transacao_duplicada:
                           continue

                     conexao = conectar_banco()
                     cursor = conexao.cursor()

                     if tipo_importado == termo_gasto:

                         novo_gasto = {
                           "id_transacao": str(uuid.uuid4()),
                           "id_usuario": st.session_state.usuario_atual["id_usuario"],
                           "data": data_importada,
                           "descricao": descricao_importada,
                           "valor": valor_importado,
                           "categoria": categoria_importada
                        }

                         cursor.execute(
                            """
                            INSERT INTO dbo.gastos(
                            id_transacao,
                            id_usuario,
                            data,
                            descricao,
                            valor,
                            categoria,
                            classificacao)
                            VALUES (?,?,?,?,?,?,?)
                            """,
                         novo_gasto["id_transacao"],
                         novo_gasto["id_usuario"],
                         novo_gasto["data"],
                         novo_gasto["descricao"],
                         novo_gasto["valor"],
                         novo_gasto["categoria"],
                         classificacao_importada
                         )

                     else:

                         nova_receita = {
                           "id_transacao": str(uuid.uuid4()),
                           "id_usuario": st.session_state.usuario_atual["id_usuario"],
                           "data": data_importada,
                           "descricao": descricao_importada,
                           "valor": valor_importado,
                           "categoria": categoria_importada
                        }

                         cursor.execute(
                                  """
                                  INSERT INTO dbo.receitas(
                                  id_transacao,
                                  id_usuario,
                                  data,
                                  descricao,
                                  valor,
                                  categoria,
                                  classificacao)
                                  VALUES (?,?,?,?,?,?,?)
                                  """,
                         nova_receita["id_transacao"],
                         nova_receita["id_usuario"],
                         nova_receita["data"],
                         nova_receita["descricao"],
                         nova_receita["valor"],
                         nova_receita["categoria"],
                         classificacao_importada
                         )




                     conexao.commit()
                     cursor.close()
                     conexao.close()

                     quantidade_importada += 1



                  st.session_state.importacao_sucesso = quantidade_importada
                  st.rerun()
