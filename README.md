# Robô Emitente de Boletos

Projeto para automação de emissão de boletos sindicais (login, geração, captura do boleto em PDF e organização do arquivo final).

## Requisitos

- `Python 3.12` (obrigatório para este projeto)
- Google Chrome instalado
- Dependências do `requirements.txt`

## Instalação (modo código)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Instalador pronto

Se você não quiser rodar pelo código, use o instalador já disponível na pasta:

- `installer`

## Como executar

### Modo padrão (CLI)

```powershell
python main.py
```

### Modo interface gráfica (UI)

```powershell
python main.py --ui
```

## Flags disponíveis

- `--ui`: abre a interface gráfica (CustomTkinter).
- `--full`: fluxo completo (reservado para evolução do fluxo; já existe no parser).
- `--pause`: pausa ao final para manter o navegador aberto.

Exemplo:

```powershell
python main.py --ui --pause
```

## Estrutura resumida

- `main.py`: ponto de entrada da aplicação.
- `src/boleto_bot/ui`: interface gráfica.
- `src/boleto_bot/automation`: runner e controle do navegador.
- `src/boleto_bot/portals`: regras e seletores por sindicato.
- `installer`: arquivos do instalador.

## Como a estrutura funciona

Fluxo principal:

1. `main.py` inicializa o projeto e chama o CLI.
2. `src/boleto_bot/cli.py` lê as flags e decide entre modo CLI ou UI.
3. No modo UI, `src/boleto_bot/ui/app.py` sobe a janela e `MainScreen`.
4. Os dados dos boletos viram requests validadas em `src/boleto_bot/domain/validators.py`.
5. `src/boleto_bot/automation/flow_runner.py` executa cada request.
6. O runner escolhe o portal correto em `src/boleto_bot/services/portal_registry.py`.
7. Cada portal em `src/boleto_bot/portals/` faz o fluxo do sindicato (login, contribuicao, boleto).
8. O PDF final e salvo/organizado por `src/boleto_bot/services/storage_service.py`.

Responsabilidade por pasta:

- `src/boleto_bot/domain`: modelos, enums e validacoes de negocio.
- `src/boleto_bot/automation`: orquestracao da execucao e browser/download.
- `src/boleto_bot/portals`: implementacao especifica de cada sindicato.
- `src/boleto_bot/services`: suporte de storage, relatorio e registry de portal.
- `src/boleto_bot/ui`: telas e componentes da interface grafica.
- `src/boleto_bot/config`: configuracoes lidas por variaveis de ambiente.

## Observações

- O projeto foi desenvolvido para ambiente Windows/PowerShell.
- Saída dos boletos e arquivos auxiliares seguem as configurações de `Settings` (`src/boleto_bot/config/settings.py`).
