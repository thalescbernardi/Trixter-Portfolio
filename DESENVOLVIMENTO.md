# Desenvolvimento local

## Testes no Windows (PowerShell)

Use o Python do ambiente em que as dependências de `requirements-testes.txt`
estão instaladas. Na raiz do repositório, execute:

```powershell
$env:PYTHONUTF8 = '1'
python -m pytest -q --basetemp .test-temp-local
```

A variável vale para esta sessão do terminal e é herdada pelos subprocessos.
Ela evita incompatibilidades entre a codificação padrão do Windows e o UTF-8
usado pelo Streamlit ao ler os scripts temporários gerados pelo `AppTest`.
Não exige alteração no código de produção nem nos testes.

`--basetemp` direciona os temporários do pytest para uma pasta local, já coberta
pelo padrão `.test-temp-*/` do `.gitignore`. O pytest pode apagar e recriar essa
pasta: use um nome novo por execução se precisar preservar os temporários de
uma execução anterior. Nunca aponte essa opção para uma pasta com outros dados.

Se `python` resolver para um alias da Microsoft Store ou outro ambiente, use
o caminho completo do interpretador correto no lugar de `python`.
