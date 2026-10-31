"""Promoção da imagem do executor só com os digests esperados."""
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest


RAIZ = Path(__file__).resolve().parents[1]
WORKFLOW = RAIZ / "docs" / "workflows" / "imagem-envios.yml"
REGISTRO = "ghcr.io/usuario-exemplo/trixter-envios"
LATEST = f"{REGISTRO}:latest"
SHA = "235c59f9500549786e050e8acf18ee910209a2a3"
ANTERIOR = "sha256:e01b52b9630f147ce93eb3eafcf60abbd49a76e0245857d69d44982ec5f9c15d"
ORIGEM = "sha256:ae81ef312c5da6e0245ac456643fcd1dfd535544a083eb013632a67d010ef222"
OUTRO = "sha256:" + ("ab" * 32)

_WRAPPER = r"""#!/bin/bash
docker() {
  printf '%s\n' "$*" >> "$DOCKER_CHAMADAS"
  if [ "$1" != "buildx" ] || [ "$2" != "imagetools" ]; then
    echo "comando docker inesperado: $*" >&2
    return 1
  fi
  if [ "$3" = "create" ]; then
    return 0
  fi
  if [ "$3" != "inspect" ]; then
    echo "subcomando docker inesperado: $*" >&2
    return 1
  fi
  ref="$4"
  if [ "$ref" = "$LATEST" ]; then
    n=0
    if [ -f "$DOCKER_VEZES_LATEST" ]; then
      IFS= read -r n < "$DOCKER_VEZES_LATEST" || n=0
    fi
    n=$((n + 1))
    printf '%s\n' "$n" > "$DOCKER_VEZES_LATEST"
    if [ "$n" -eq 1 ] && [ -n "${DOCKER_FALHA_LATEST:-}" ]; then
      if [ "$DOCKER_FALHA_LATEST" = "ausente" ]; then
        echo "manifest unknown" >&2
      else
        echo "unauthorized: authentication required" >&2
      fi
      return 1
    fi
    if [ "$n" -eq 2 ] && [ -n "${DOCKER_RELEITURA:-}" ]; then
      if [ "$DOCKER_RELEITURA" = "falha" ]; then
        echo "unauthorized: authentication required" >&2
        return 1
      fi
      printf 'Digest: %s\n' "$DOCKER_RELEITURA"
      return 0
    fi
    if [ "$n" -ge 3 ] && [ -n "${DOCKER_LATEST_FINAL:-}" ]; then
      printf 'Digest: %s\n' "$DOCKER_LATEST_FINAL"
      return 0
    fi
  elif [ -n "${DOCKER_FALHA_ORIGEM:-}" ]; then
    echo "manifest unknown" >&2
    return 1
  fi
  digest=""
  while IFS=' ' read -r chave valor; do
    if [ "$chave" = "$ref" ]; then
      digest="$valor"
      break
    fi
  done < "$DOCKER_MAPA"
  if [ -z "$digest" ]; then
    echo "manifest unknown" >&2
    return 1
  fi
  printf 'Digest: %s\n' "$digest"
}
source "$PROMOTER_SCRIPT"
"""


def _texto():
    return WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")


def _job(nome):
    texto = _texto()
    marcador = f"\n  {nome}:\n"
    inicio = texto.index(marcador)
    resto = texto[inicio + 1:]
    proximo = re.search(r"\n  [a-z0-9_]+:\n", resto)
    if proximo is None:
        return texto[inicio:]
    return texto[inicio:inicio + 1 + proximo.start()]


def _script_promover():
    texto = _texto()
    marcador = "      - name: Promover a origem para latest\n        run: |\n"
    inicio = texto.index(marcador) + len(marcador)
    linhas = []
    for linha in texto[inicio:].split("\n"):
        if linha == "":
            linhas.append("")
            continue
        if not linha.startswith("          "):
            break
        linhas.append(linha[10:])
    while linhas and linhas[-1] == "":
        linhas.pop()
    return "\n".join(linhas) + "\n"


def _bash():
    encontrado = shutil.which("bash")
    if encontrado:
        return encontrado
    for candidato in (
        Path(r"C:\Program Files\Git\bin\bash.exe"),
        Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
    ):
        if candidato.exists():
            return str(candidato)
    pytest.fail("O bash não está disponível para executar o script de promoção.")


def _executar(tmp_path, referencia, esperado_latest, esperado_origem, mapa, **extras):
    script = tmp_path / "promover.sh"
    script.write_text(_script_promover(), encoding="utf-8", newline="\n")
    mapa_arq = tmp_path / "mapa.txt"
    mapa_arq.write_text(
        "".join(f"{ref} {digest}\n" for ref, digest in mapa),
        encoding="utf-8",
        newline="\n",
    )
    resumo = tmp_path / "resumo.md"
    wrapper = tmp_path / "executar.sh"
    wrapper.write_text(_WRAPPER, encoding="utf-8", newline="\n")
    env = os.environ.copy()
    env.update({
        "REFERENCIA": referencia,
        "DIGEST_LATEST_ESPERADO": esperado_latest,
        "DIGEST_ORIGEM_ESPERADO": esperado_origem,
        "LATEST": LATEST,
        "GITHUB_STEP_SUMMARY": resumo.as_posix(),
        "DOCKER_CHAMADAS": (tmp_path / "chamadas.txt").as_posix(),
        "DOCKER_VEZES_LATEST": (tmp_path / "vezes.txt").as_posix(),
        "DOCKER_MAPA": mapa_arq.as_posix(),
        "PROMOTER_SCRIPT": script.as_posix(),
    })
    env.update(extras)
    concluido = subprocess.run(
        [_bash(), wrapper.as_posix()],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        encoding="utf-8",
    )
    chamadas_arq = tmp_path / "chamadas.txt"
    chamadas = chamadas_arq.read_text(encoding="utf-8") if chamadas_arq.exists() else ""
    texto_resumo = resumo.read_text(encoding="utf-8") if resumo.exists() else ""
    return concluido, chamadas, texto_resumo


def _mapa(latest=ANTERIOR, origem=ORIGEM):
    return [
        (LATEST, latest),
        (f"{REGISTRO}:{SHA}", origem),
        (f"{REGISTRO}@{origem}", origem),
    ]


def test_inputs_de_digest_sao_opcionais_na_interface_e_obrigatorios_no_script():
    texto = _texto()
    for nome in ("digest_origem_esperado", "digest_latest_esperado"):
        inicio = texto.index(f"      {nome}:\n")
        bloco = texto[inicio:inicio + 350]
        assert "required: false" in bloco
        assert 'default: ""' in bloco
    promover = _job("promover")
    assert "DIGEST_ORIGEM_ESPERADO: ${{ inputs.digest_origem_esperado }}" in promover
    assert "DIGEST_LATEST_ESPERADO: ${{ inputs.digest_latest_esperado }}" in promover
    assert "inputs.operacao == 'Promover'" in promover


@pytest.mark.parametrize(
    ("esperado_latest", "esperado_origem", "mensagem"),
    [
        ("", ORIGEM, "o digest esperado de latest deve ser sha256:"),
        (ANTERIOR, "", "o digest esperado da origem deve ser sha256:"),
        ("sha256:" + ANTERIOR.split(":", 1)[1].upper(), ORIGEM, "o digest esperado de latest deve ser sha256:"),
        (ANTERIOR[:-1], ORIGEM, "o digest esperado de latest deve ser sha256:"),
        (ANTERIOR, "ae81ef312c5da6e0245ac456643fcd1dfd535544a083eb013632a67d010ef222", "o digest esperado da origem deve ser sha256:"),
        (ANTERIOR, ANTERIOR, "os digests esperados são iguais"),
    ],
)
def test_promover_rejeita_digests_invalidos_ou_iguais(tmp_path, esperado_latest, esperado_origem, mensagem):
    concluido, chamadas, resumo = _executar(
        tmp_path, SHA, esperado_latest, esperado_origem, [],
    )
    assert concluido.returncode == 1, concluido.stderr
    assert mensagem in resumo
    assert chamadas == ""
    assert "Nenhuma promoção foi feita." in resumo


def test_promover_rejeita_referencia_invalida_sem_escrever(tmp_path):
    concluido, chamadas, resumo = _executar(
        tmp_path, "abc", ANTERIOR, ORIGEM, [],
    )
    assert concluido.returncode == 1, concluido.stderr
    assert "a referência deve ser um SHA de 40 caracteres" in resumo
    assert chamadas == ""


def test_promover_bloqueia_latest_diferente_do_esperado(tmp_path):
    concluido, chamadas, resumo = _executar(
        tmp_path, SHA, ANTERIOR, ORIGEM, _mapa(latest=OUTRO),
    )
    assert concluido.returncode == 1, concluido.stderr
    assert "latest não está no digest anterior esperado" in resumo
    assert "imagetools create" not in chamadas


def test_promover_bloqueia_origem_diferente_da_esperada(tmp_path):
    concluido, chamadas, resumo = _executar(
        tmp_path, SHA, ANTERIOR, ORIGEM, _mapa(origem=OUTRO),
    )
    assert concluido.returncode == 1, concluido.stderr
    assert "a origem não está no digest esperado" in resumo
    assert "imagetools create" not in chamadas


def test_promover_interrompe_se_a_consulta_de_latest_falha(tmp_path):
    concluido, chamadas, resumo = _executar(
        tmp_path, SHA, ANTERIOR, ORIGEM, _mapa(), DOCKER_FALHA_LATEST="autenticacao",
    )
    assert concluido.returncode == 1, concluido.stderr
    assert "falhou ao consultar latest por autenticação ou comunicação" in resumo
    assert "imagetools create" not in chamadas


def test_promover_interrompe_se_a_releitura_diverge(tmp_path):
    concluido, chamadas, resumo = _executar(
        tmp_path, SHA, ANTERIOR, ORIGEM, _mapa(), DOCKER_RELEITURA=OUTRO,
    )
    assert concluido.returncode == 1, concluido.stderr
    assert "latest mudou depois da primeira leitura" in resumo
    assert "imagetools create" not in chamadas


def test_atalho_nao_dispensa_o_digest_anterior_quando_latest_ja_e_a_origem(tmp_path):
    concluido, chamadas, resumo = _executar(
        tmp_path, SHA, ANTERIOR, ORIGEM, _mapa(latest=ORIGEM, origem=ORIGEM),
    )
    assert concluido.returncode == 1, concluido.stderr
    assert "latest não está no digest anterior esperado" in resumo
    assert "já apontava para o digest solicitado" not in resumo
    assert "imagetools create" not in chamadas


def test_verificacoes_acontecem_antes_do_imagetools_create():
    script = _script_promover()
    marcos = [
        "64 hexadecimais minúsculos",
        "os digests esperados são iguais",
        'imagetools inspect "$LATEST"',
        "digest anterior esperado",
        'imagetools inspect "$origem"',
        "a origem não está no digest esperado",
        "latest já apontava para o digest solicitado",
        "imediatamente antes da promoção",
        "imagetools create --prefer-index=false",
        "a verificação final divergiu",
    ]
    posicoes = [script.index(marco) for marco in marcos]
    assert posicoes == sorted(posicoes)
    assert script.count("exit 0") == 1


def test_publicar_permanece_sem_os_digests_esperados():
    publicar = _job("publicar")
    assert "inputs.operacao == 'Publicar'" in publicar
    assert "ghcr.io/usuario-exemplo/trixter-envios:${{ github.sha }}" in publicar
    assert 'docker push "$IMAGE"' in publicar
    assert "o envio de latest foi recusado nesta operação." in publicar
    assert "imagetools create" not in publicar
    assert "digest_origem_esperado" not in publicar
    assert "digest_latest_esperado" not in publicar
    assert "DIGEST_ORIGEM_ESPERADO" not in publicar
    assert "DIGEST_LATEST_ESPERADO" not in publicar


def test_workflow_nao_recebe_credenciais_novas():
    texto = _texto()
    assert texto.count("${{ secrets.GITHUB_TOKEN }}") == 2
    assert texto.count("${{ secrets.") == 2
    assert texto.count("password-stdin") == 2
    assert "group: trixter-envios-latest" in texto
    assert "cancel-in-progress: false" in texto
    assert "packages: write" in texto
    assert "contents: read" in texto
    assert "AZURE_" not in texto
    assert "TRIXTER_DATABASE" not in texto
    assert "TRIXTER_EMAIL" not in texto
    assert "id-token:" not in texto


def test_promocao_escreve_somente_depois_que_os_digests_conferem(tmp_path):
    concluido, chamadas, resumo = _executar(
        tmp_path,
        SHA,
        ANTERIOR,
        ORIGEM,
        _mapa(),
        DOCKER_LATEST_FINAL=ORIGEM,
    )
    assert concluido.returncode == 0, concluido.stderr + concluido.stdout
    assert "latest foi promovida para o digest resolvido antes da operação." in resumo
    linhas = [linha for linha in chamadas.splitlines() if linha]
    create = next(i for i, linha in enumerate(linhas) if "imagetools create" in linha)
    anteriores = linhas[:create]
    assert sum("imagetools inspect" in linha for linha in anteriores) == 3
    assert sum(LATEST in linha and "inspect" in linha for linha in anteriores) == 2
    assert linhas[create] == (
        f"buildx imagetools create --prefer-index=false --tag {LATEST} {REGISTRO}@{ORIGEM}"
    )
