<p align="center">
    <img height="100" align="center" alt="netstat-logo" src="assets/NS_logo_long.png" />
<p/>

O NetStat Monitor coleta e analisa métricas de rede em tempo real. Ele mede latência, jitter e perda de pacotes por ping, registra as medições em CSV e apresenta gráficos, estatísticas e relatórios em um painel interativo.

Com o objetivo de facilitar o reconhecimento de possíveis pontos de falha, o NetStat Monitor possibilita o monitoramento simultâneo de destinos nas camadas LAN, MAN e WAN. Permitindo ao usuário determinar se o problema pode ser resolvido pessoalmente ou pela provedora. O sistema pode detectar o gateway e um host externo automaticamente, ou aceitar hosts informados pelo usuário.

## Instalação e uso

### Windows: instalador

Baixe o instalador `NetStat-Monitor-*-windows-x64-setup.exe` na página de [Releases](https://github.com/Coastburgh/NetStat-Monitor/releases), execute-o e abra **NetStat Monitor** pelo menu Iniciar. O instalador é destinado ao Windows 10 ou superior em arquitetura x64. Se necessário, ele instala o Microsoft Edge WebView2 durante a instalação. Não é preciso instalar Python para usar essa versão.

### Linux: uso pelo código-fonte

O sistema já pode ser usado no Linux pelo código-fonte. É necessário Python 3.12 ou superior, `pip` e os comandos de rede `ping`, `ip` e `tracepath` para a coleta e a detecção automática. Também é recomendado a instalação das dependências em um ambiente virtual. Execute os comandos a seguir em um terminal:

```bash
git clone https://github.com/Coastburgh/NetStat-Monitor.git
cd NetStat-Monitor
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

O painel abre no navegador. Uma versão de instalação simplificada para Arch Linux está em desenvolvimento; ainda não há pacote ou instalador Linux publicado.

### Primeiros passos no painel

1. Informe os hosts LAN, MAN e WAN ou use a detecção automática. O tipo de conexão (Wi-Fi ou Ethernet) também pode ser detectado.
2. Ajuste o intervalo e inicie a coleta. É possível interrompê-la pelo painel.
3. Consulte os gráficos de latência, jitter e perda de pacotes e os indicadores estatísticos.
4. Gere o relatório consolidado e visualize ou exporte o resultado em Markdown, PDF ou HTML.

## Como o sistema funciona

O painel Streamlit controla a coleta de vários hosts em threads. Cada coletor executa `ping` periodicamente, calcula as métricas e entrega as medições ao armazenamento por callback. Os dados em CSV alimentam as visualizações, as estatísticas descritivas, a detecção de outliers por IQR, a correlação entre horário e latência e o relatório consolidado.

### Dados e configurações

Cada linha de CSV representa uma medição:

    timestamp,host,latencia_ms,jitter_ms,perda_pacotes_pct

O tipo de conexão fica no nome do arquivo, no formato `{rotulo_camada}_{host}_{rotulo_sessao}.csv`, por exemplo `wan_8.8.8.8_wifi.csv`. Os rótulos de camada são `lan`, `man` e `wan`; os de sessão são `wifi` e `ethernet`. A coluna `tipo_conexao` é reconstruída ao carregar os dados.

Por padrão, a execução pelo código-fonte usa o ambiente `desenvolvimento`. Os dados são gravados no perfil do usuário:

| Sistema | Desenvolvimento (padrão) | Produção |
|---|---|---|
| Windows | `%LOCALAPPDATA%\NetStat-Dev\dados` | `%LOCALAPPDATA%\NetStat\dados` |
| Linux | `~/.local/share/netstat-dev/dados` | `~/.local/share/netstat/dados` |
| macOS | `~/Library/Application Support/NetStat-Dev/dados` | `~/Library/Application Support/NetStat/dados` |

No Linux, um `XDG_DATA_HOME` absoluto substitui a base `~/.local/share`. No Windows, se `LOCALAPPDATA` estiver ausente ou não for absoluto, a base utilizada é `~/AppData/Local`.

Os hosts, o tipo de conexão, o intervalo e o modo automático são salvos em `configuracao.json` na pasta de dados. Os relatórios ficam na subpasta `relatorios/`. Ao reiniciar, os campos são restaurados, mas a coleta permanece parada. Arquivo ausente usa valores padrão; falhas de leitura ou gravação são informadas no painel. Se a gravação falhar, os valores permanecem em memória durante a execução.

## Desenvolvimento

### Obter o código e instalar dependências

Use Python 3.12 ou superior e `pip`. Os comandos abaixo pressupõem execução na raiz do projeto.

```bash
git clone https://github.com/Coastburgh/NetStat-Monitor.git
cd NetStat-Monitor
python -m venv .venv
```

Ative o ambiente virtual e instale as dependências:

| Sistema | Ativação |
|---|---|
| Windows PowerShell | `.\.venv\Scripts\Activate.ps1` |
| Windows cmd.exe | `.venv\Scripts\activate.bat` |
| Linux/macOS | `source .venv/bin/activate` |

```bash
python -m pip install -r requirements.txt
```

No PowerShell, se a execução de scripts estiver bloqueada, use `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` ou ative o ambiente no `cmd.exe`. `requirements.txt` contém as dependências diretas do painel; `requirements-desktop.txt` acrescenta as dependências do inicializador Windows e `requirements-build.txt` as de empacotamento.

### Executar e testar

```bash
python -m streamlit run app.py
python -m unittest discover -s tests -q
```

Com a `.venv` ativada, esses são os comandos de execução e teste para Windows, Linux e macOS. A execução nativa no macOS ainda não foi validada. Sem ativá-la, use `.\.venv\Scripts\python.exe` no Windows ou `.venv/bin/python` no Linux e macOS no lugar de `python`. Os testes usam diretórios temporários para isolar os arquivos gerados.

Para executar módulos específicos:

```bash
python -m coletor.deteccao_rede
python -m coletor.ping_collector
python -m analise.gerar_relatorio
```

O primeiro comando testa a detecção de rede; o segundo, a coleta direta; o terceiro gera o relatório consolidado pelo terminal.

### Configuração do ambiente e dos dados

`NETSTAT_AMBIENTE` aceita `desenvolvimento` ou `producao` (sem acento). Ausente ou vazia, usa `desenvolvimento`. Para iniciar em produção:

```powershell
$env:NETSTAT_AMBIENTE = "producao"
python -m streamlit run app.py
Remove-Item Env:NETSTAT_AMBIENTE
```

```bash
NETSTAT_AMBIENTE=producao python -m streamlit run app.py
```

O primeiro exemplo é para Windows PowerShell; o segundo, para Linux/macOS. `NETSTAT_PASTA_DADOS` define diretamente uma pasta de dados absoluta e tem prioridade sobre `NETSTAT_AMBIENTE`. A escolha é lida no início do processo, portanto mudanças exigem reinicialização. Os dados antigos na pasta `dados/` do projeto não são movidos nem excluídos automaticamente. Para continuar usando essa pasta:

```powershell
$env:NETSTAT_PASTA_DADOS = (Resolve-Path .\dados).Path
python -m streamlit run app.py
Remove-Item Env:NETSTAT_PASTA_DADOS
```

```bash
NETSTAT_PASTA_DADOS="$(pwd)/dados" python -m streamlit run app.py
```

No PowerShell, `Resolve-Path` exige que a pasta já exista. Os exemplos pressupõem a `.venv` ativada.

### Arquitetura do projeto

- `app.py` — entrada do painel Streamlit e navegação;
- `desktop.py` — inicializador da interface Windows;
- `paginas/` — páginas Monitor e Relatório;
- `coletor/` — coleta por ping, controle de threads e detecção de rede;
- `armazenamento/` — persistência em CSV e configurações;
- `analise/` — estatísticas, identificação de padrões e relatório;
- `visualizacao/` — gráficos;
- `scripts/` — utilitários, incluindo geração de dados simulados e do instalador Windows;
- `tests/` — testes automatizados.

As pastas de código possuem `__init__.py`.

## Limitações do sistema e dos métodos

### Capacidades e plataformas

- Há instalador apenas para Windows x64. Linux já funciona pelo código-fonte; a instalação simplificada para Arch Linux está em desenvolvimento. No macOS, há caminho de execução pelo código-fonte, mas a execução nativa ainda não foi validada.
- A aplicação usa ping para diagnóstico prático; não captura nem inspeciona pacotes e não substitui ferramentas especializadas. O armazenamento é exclusivamente em CSV.
- Comparações estatísticas entre Wi-Fi e Ethernet ainda não foram aprofundadas. A validação com coletas extensivas em múltiplos dias está pendente.

### Detecção e análise

- A camada MAN é uma aproximação obtida pelo primeiro host externo em `traceroute`/`tracepath`; não identifica com precisão o provedor. No Linux, `tracepath` pode omitir a resposta do primeiro roteador externo e retornar o salto seguinte. Se a detecção falhar, os hosts podem ser informados manualmente.
- A classificação automática de Wi-Fi e Ethernet usa a interface da rota padrão. Interfaces virtuais, como VPN e tethering, não são classificadas.
- A detecção de outliers usa IQR; os histogramas, o teste t, o z-score e a comparação com o modelo M/M/1 não fazem parte do escopo confirmado. As médias por minuto servem à visualização, enquanto os outliers são calculados sobre as medições sem essa agregação.
- A perda de pacotes exibida nos gráficos é calculada por janela de tempo, e não por um contador acumulado entre sessões. Taxas elevadas de outliers em hotspots móveis podem refletir as características dessa rede.

## Contexto acadêmico

Projeto Integrador 2026/2 — Faculdade de Princípios Militares.

Equipe: Eduardo Costa Borges, Cid Mendes, João P. Pereira, Fernando Ferreira Vaz, Tamynne Vitória e Paulo Carrijo. Professor: Leonardo A. Portes.

O acompanhamento de destinos LAN, MAN e WAN relaciona o projeto ao conteúdo de Introdução a Redes de Computadores. A análise das medições aplica conceitos de estatística descritiva e correlação.

### Relação com as disciplinas

| Tópico da ementa | Onde aparece no projeto |
|---|---|
| Medidas de posição e dispersão | Estatística descritiva (req. 11) |
| Distribuições de probabilidade | Não coberto; dependia da comparação com Teoria das Filas, fora do escopo confirmado |
| Correlação | Correlação entre horário do dia e latência (req. 14) |
| Testes de hipóteses (Z, t) | Removidos do escopo confirmado (req. 12 e 15) |
| Tipos de rede (LAN, MAN, WAN) | Hosts organizados e detectados por camada |
| Comandos de diagnóstico (ping, traceroute, ipconfig) | Base da coleta e da detecção de hosts |
| Protocolos (ICMP) | Utilizado na coleta via ping |
| Análise de pacotes com Wireshark | Atividade manual complementar, não incorporada ao código |

### Decisões metodológicas e evolução

- O IQR foi escolhido para identificar outliers porque as distribuições de latência tendem a ser assimétricas e valores extremos podem mascarar a detecção por z-score.
- A agregação por minuto suaviza os gráficos, mas não é usada para detectar outliers, pois poderia ocultar picos reais.
- O painel Streamlit passou a controlar a coleta; o antigo `main.py` de terminal foi descontinuado e sua lógica multi-host foi incorporada ao `app.py`.
- O projeto manteve CSV como formato de armazenamento. SQLite, histogramas, teste t e comparação com M/M/1 foram avaliados e retirados do escopo confirmado.
- Permanecem pendentes o aprofundamento da comparação Wi-Fi/Ethernet, o refinamento das visualizações e a inspeção manual de tráfego com Wireshark.

## Licença

[Licença MIT](LICENSE). Projeto desenvolvido em contexto universitário.
