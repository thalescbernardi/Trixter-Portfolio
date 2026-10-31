"""Cálculos e PDF do relatório mensal, sem interface ou estado de sessão."""
from datetime import date
from io import BytesIO
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

COR_FUNDO = HexColor("#F7F5F0")
MESES = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
         "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")

def formatar_moeda(valor):
    numero = float(valor)
    texto = f"{abs(numero):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if numero < 0:
        return f"-R$ {texto}"
    return f"R$ {texto}"

def desenhar_fundo(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(COR_FUNDO)
    canvas.rect(
        0,
        0,
        A4[0],
        A4[1],
        fill=1,
        stroke=0
    )
    canvas.restoreState()

def gerar_pdf_relatorio(
    mes_selecionado,
    ano_selecionado,
    total_receitas_relatorio,
    total_gastos_relatorio,
    saldo_relatorio,
    taxa_poupanca_relatorio,
    termo_gasto,
    gastos_por_categoria,
    percentual_por_categoria,
    variacao_receitas,
    variacao_gastos,
    principal_categoria,
    valor_principal_categoria,
    percentual_principal_categoria
):
   buffer = BytesIO()

   documento = SimpleDocTemplate(
      buffer,
      pagesize=A4
   )

   estilos = getSampleStyleSheet()

   from reportlab.lib import colors
   from reportlab.lib.styles import ParagraphStyle

   estilo_titulo_trixter = ParagraphStyle(
      "TituloTrixter",
      parent=estilos["Title"],
      textColor=colors.HexColor("#D4AF37"),
      fontSize=24,
      leading=22,
      spaceAfter=18

   )

   estilo_secao = ParagraphStyle(
      "SecaoTrixter",
      parent=estilos["Heading2"],
      textColor=colors.HexColor("#A67C00"),
      fontsize=15,
      leading=18,
      spaceBefore=10,
      spaceAfter=8
   )

   estilo_centralizado = ParagraphStyle(
      "Centralizado",
      parent=estilos["Normal"],
      alignment=TA_CENTER
   )

   elementos = []

   titulo= Paragraph(
      "TRIXTER - Relatório Mensal",
      estilo_titulo_trixter
    )

   cabecalho = Table(
      [[titulo]],
      colWidths=[450]
   )

   cabecalho.setStyle(
      TableStyle([
         ("BACKGROUND", (0,0), (-1, -1), colors.HexColor("#26374A")),
         ("TOPPADDING", (0,0), (-1, -1), 18),
         ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
         ("LEFTPADDING", (0, 0), (-1, -1), 15),
         ("RIGHTPADDING", (0, 0), (-1, -1), 15),
    ])
   )

   elementos.append(cabecalho)
   elementos.append(Spacer(1, 20))



   elementos.append(
    Paragraph(
        f"Período: {mes_selecionado}/{ano_selecionado}",
        estilo_secao
    )
)

   resumo_financeiro = Table(
    [
        [
            Paragraph("<b>Receitas</b>", estilo_centralizado),
            Paragraph(f"<b>{termo_gasto}s</b>", estilo_centralizado),
            Paragraph("<b>Saldo</b>", estilo_centralizado),
            Paragraph("<b>Taxa de poupança</b>", estilo_centralizado),
        ],
        [
            Paragraph(
                formatar_moeda(total_receitas_relatorio),
                estilo_centralizado
            ),
            Paragraph(
                formatar_moeda(total_gastos_relatorio),
                estilo_centralizado
            ),
            Paragraph(
                formatar_moeda(saldo_relatorio),
                estilo_centralizado
            ),
            Paragraph(
                f"{taxa_poupanca_relatorio:.1f}%".replace(".", ","),
                estilo_centralizado
            ),
        ],
    ],
    colWidths=[112, 112, 112, 112]
)

   resumo_financeiro.setStyle(
     TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F5F5")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#6B6B6B")),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#222222")),

        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 12),


        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B8B8B8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B8B8B8")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#B8B8B8")),
    ])
)

   elementos.append(resumo_financeiro)


   elementos.append(Spacer(1,20))



   elementos.append(
      Paragraph(
         f"{termo_gasto}s por categoria",
         estilo_secao
      )
   )

   dados_categorias = []

   dados_categorias.append([
    Paragraph("<b>Categoria</b>", estilo_centralizado),
    Paragraph("<b>Valor</b>", estilo_centralizado),
    Paragraph("<b>Percentual</b>", estilo_centralizado)
   ])

   for categoria, valor in gastos_por_categoria.items():

      percentual = percentual_por_categoria[categoria]

      dados_categorias.append([
         Paragraph(
               f"<b>{categoria}</b>",
               estilo_centralizado
         ),
         Paragraph(
               formatar_moeda(valor),
               estilo_centralizado
         ),
         Paragraph(
               f"{percentual:.1f}%".replace(".", ","),
               estilo_centralizado
         )
      ])

   if dados_categorias:

      tabela_categorias = Table(
         dados_categorias,
         colWidths=[220,120,108]
      )

      tabela_categorias.setStyle(
         TableStyle([

            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F5F5")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),

            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),

            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),

            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B8B8B8")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B8B8B8"))
         ])
      )

      elementos.append(tabela_categorias)

   else:
      elementos.append(
         Paragraph(
            f"Nenhum {termo_gasto.lower()} registrado no período.",
            estilo_centralizado
         )
      )



   elementos.append(Spacer(1,20))

   elementos.append(
      Paragraph(
         "Comparação com o mês anterior ",
         estilo_secao
      )
   )

   if variacao_receitas is not None:
    texto_receitas = f"{variacao_receitas:+.1f}%"
   else:
    texto_receitas = "Sem comparação"



   if variacao_gastos is not None:
    texto_gastos = f"{variacao_gastos:+.1f}%"
   else:
    texto_gastos = "Sem comparação"

   dados_comparacao = [
    ["Indicador", "Variação"],
    ["Receitas", texto_receitas],
    [f"{termo_gasto}s", texto_gastos]
]

   tabela_comparacao = Table(
      dados_comparacao,
      colWidths=[225, 225]
   )

   tabela_comparacao.setStyle(
      TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F5F5")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),

        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),

        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),

        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B8B8B8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B8B8B8")),
    ])
)

   elementos.append(tabela_comparacao)

   elementos.append(Spacer(1, 20))

   elementos.append(
    Paragraph(
        "Destaque do mês",
        estilo_secao
    )
)

   if principal_categoria is not None:

    estilo_destaque = ParagraphStyle(
       "Destaque",
       parent=estilo_centralizado,
       fontSize=9,
       leading=11
    )
    texto_destaque = Paragraph(
            f"A categoria com maior {termo_gasto.lower()} no período foi "
            f"{principal_categoria}, com "
            f"{formatar_moeda(valor_principal_categoria)}, "
            f"representando {percentual_principal_categoria:.1f}% "
            f"do total.",
            estilo_destaque
        )
    tabela_destaque = Table(
       [[texto_destaque]],
       colWidths=[450]
        )

    tabela_destaque.setStyle(
    TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),

        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B8B8B8")),
      ])
      )
    elementos.append(tabela_destaque)

   else:
    elementos.append(
        Paragraph(
            f"Não houve {termo_gasto.lower()}s no período selecionado.",
            estilo_centralizado
        )
    )

   documento.build(
      elementos,
      onFirstPage=desenhar_fundo,
      onLaterPages=desenhar_fundo
      )

   buffer.seek(0)
   #Volta ao começo do pdf pra ler desde o inicio.

   return buffer

def mes_anterior(ano, mes):
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


def calcular_relatorio_mensal(cursor, id_usuario, ano, mes):
    """Usa o mesmo período para todos os indicadores e para o cabeçalho do PDF."""
    inicio = date(ano, mes, 1)
    fim = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)
    ano_anterior, mes_ant = mes_anterior(ano, mes)
    inicio_anterior = date(ano_anterior, mes_ant, 1)

    def total(tabela, de, ate):
        # tabela vem exclusivamente das constantes abaixo, nunca de entrada externa.
        cursor.execute(
            f"SELECT COALESCE(SUM(valor), 0) FROM dbo.{tabela} "
            "WHERE id_usuario = ? AND data >= ? AND data < ?",
            id_usuario, de, ate,
        )
        return float(cursor.fetchone()[0])

    receitas = total("receitas", inicio, fim)
    gastos = total("gastos", inicio, fim)
    receitas_anteriores = total("receitas", inicio_anterior, inicio)
    gastos_anteriores = total("gastos", inicio_anterior, inicio)
    cursor.execute(
        "SELECT categoria, SUM(valor) FROM dbo.gastos "
        "WHERE id_usuario = ? AND data >= ? AND data < ? "
        "GROUP BY categoria ORDER BY SUM(valor) DESC",
        id_usuario, inicio, fim,
    )
    categorias = {linha[0]: float(linha[1]) for linha in cursor.fetchall()}
    percentuais = {categoria: (valor / gastos * 100 if gastos > 0 else 0.0)
                   for categoria, valor in categorias.items()}
    principal = max(categorias, key=categorias.get) if categorias else None
    return {
        "mes_selecionado": MESES[mes - 1],
        "ano_selecionado": ano,
        "total_receitas_relatorio": receitas,
        "total_gastos_relatorio": gastos,
        "saldo_relatorio": receitas - gastos,
        "taxa_poupanca_relatorio": (receitas - gastos) / receitas * 100 if receitas > 0 else 0.0,
        "gastos_por_categoria": categorias,
        "percentual_por_categoria": percentuais,
        "variacao_receitas": (receitas - receitas_anteriores) / receitas_anteriores * 100 if receitas_anteriores > 0 else None,
        "variacao_gastos": (gastos - gastos_anteriores) / gastos_anteriores * 100 if gastos_anteriores > 0 else None,
        "principal_categoria": principal,
        "valor_principal_categoria": categorias[principal] if principal is not None else 0.0,
        "percentual_principal_categoria": percentuais[principal] if principal is not None else 0.0,
    }
