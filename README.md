<p align="center">
    <img height="100" align="center" alt="netstat-logo" src="assets/NS_logo_long.png" />
<p/>

Projeto Integrador 2026/2 — Faculdade de Princípios Militares

Equipe: Eduardo Costa Borges, Cid Mendes, João P. Pereira, Fernando Ferreira Vaz, Tamynne Vitória e Paulo Carrijo
Professor: Leonardo A. Portes

---

## Visão geral

O NetStat Monitor é uma ferramenta para monitorar e analisar métricas de rede em tempo real, com foco em latência, jitter, perda de pacotes e comportamento de acesso à internet. O projeto coleta dados por ping em intervalos configuráveis, salva as medições em arquivos CSV e aplica análise estatística para caracterizar o comportamento da rede e identificar anomalias. Os resultados são apresentados em um painel interativo em Streamlit.

A ideia central é permitir que uma mesma sessão de coleta compare diferentes camadas de rede (LAN, MAN e WAN) sem depender de configuração manual de IPs em todos os casos. Para isso, o sistema inclui detecção automática do gateway e do primeiro host externo do provedor. Essa organização por camadas conecta o projeto diretamente ao tópico "Tipos de redes (LAN, MAN, WAN)" da ementa de Introdução a Redes de Computadores.

## Requisitos

- Python 3.12 ou superior, conforme os requisitos das dependências fixadas;
- pip;
- ambiente virtual recomendado.

Dependências principais: streamlit, pandas, scipy, plotly e reportlab. O arquivo `requirements.txt` contém as dependências diretas e suas versões; numpy é instalado como dependência transitiva.

## Instalação

1. Clone o repositório:

       git clone https://github.com/Coastburgh/NetStat-Monitor.git

2. Entre na pasta do projeto:

       cd NetStat-Monitor

3. Crie e ative um ambiente virtual:

   Windows (PowerShell):

       python -m venv .venv
       .\.venv\Scripts\Activate.ps1

   Caso a execução de scripts esteja bloqueada, execute uma vez:

       Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

   Como alternativa, utilize o `cmd.exe` com `.venv\Scripts\activate.bat`.

   Linux/macOS:

       python -m venv .venv
       source .venv/bin/activate

4. Instale as dependências:

       python -m pip install -r requirements.txt

## Execução

### Painel Streamlit

    python -m streamlit run app.py

Execute a partir da raiz do projeto. Os comandos com `python` pressupõem que a `.venv` esteja ativada. Sem ativá-la, utilize diretamente seu interpretador:

Windows (PowerShell):

    .\.venv\Scripts\python.exe -m streamlit run app.py

Linux/macOS:

    .venv/bin/python -m streamlit run app.py

Na interface, é possível:

- informar os hosts das camadas LAN, MAN e WAN;
- detectar automaticamente o gateway, o primeiro host externo e o tipo de conexão (Wi-Fi ou Ethernet);
- iniciar e interromper uma coleta;
- encerrar a aplicação diretamente pelo painel (botão "ENCERRAR" na barra lateral);
- visualizar gráficos de latência, jitter e perda de pacotes, além da latência instantânea da última leitura;
- gerar o relatório consolidado (req. 20) e visualizá-lo em uma página exclusiva, com preview e exportação em Markdown, PDF e HTML.

### Detecção automática de rede

Para testar apenas a detecção de hosts das camadas de rede e do tipo de conexão:

    python -m coletor.deteccao_rede

### Coleta direta

Para testes rápidos do módulo de coleta:

    python -m coletor.ping_collector

### Relatório consolidado

Para gerar o relatório consolidado diretamente pelo terminal (sem o painel):

    python -m analise.gerar_relatorio

## Dados, ambientes e configurações

Por padrão, a execução utiliza o ambiente `desenvolvimento`. Os dados são gravados no perfil do usuário, independentemente do diretório de execução:

| Sistema | Desenvolvimento (padrão) | Produção |
|---|---|---|
| Windows | `%LOCALAPPDATA%\NetStat-Dev\dados` | `%LOCALAPPDATA%\NetStat\dados` |
| Linux | `~/.local/share/netstat-dev/dados` | `~/.local/share/netstat/dados` |
| macOS | `~/Library/Application Support/NetStat-Dev/dados` | `~/Library/Application Support/NetStat/dados` |

No Linux, um `XDG_DATA_HOME` absoluto substitui a base `~/.local/share`. No Windows, se `LOCALAPPDATA` estiver ausente ou não for absoluto, a base utilizada é `~/AppData/Local`. As mudanças foram validadas manualmente no Windows e Linux; a execução nativa no macOS ainda não foi validada.

### Seleção do ambiente

`NETSTAT_AMBIENTE` aceita `desenvolvimento` e `producao` (sem acento). Ausente ou vazia, utiliza `desenvolvimento`. Para selecionar produção:

Windows (PowerShell, com a `.venv` ativada):

    $env:NETSTAT_AMBIENTE = "producao"
    python -m streamlit run app.py

Após encerrar o programa, remova a variável para voltar ao padrão nesta sessão do terminal:

    Remove-Item Env:NETSTAT_AMBIENTE

Linux/macOS (com a `.venv` ativada; a variável vale apenas para esse comando):

    NETSTAT_AMBIENTE=producao python -m streamlit run app.py

### Diretório personalizado e dados existentes

`NETSTAT_PASTA_DADOS` define diretamente a pasta de dados e tem prioridade sobre `NETSTAT_AMBIENTE`. O caminho deve ser absoluto; a variável não vazia é usada sem acrescentar outra pasta `dados`. A escolha é lida ao iniciar o processo: reinicie o programa para aplicar mudanças.

Os arquivos antigos na pasta `dados/` do projeto não são movidos nem excluídos automaticamente. Para continuar usando essa pasta:

Windows (PowerShell, com a `.venv` ativada; `Resolve-Path` exige que a pasta já exista):

    $env:NETSTAT_PASTA_DADOS = (Resolve-Path .\dados).Path
    python -m streamlit run app.py

Após encerrar o programa, remova a configuração desta sessão do terminal:

    Remove-Item Env:NETSTAT_PASTA_DADOS

Linux/macOS (com a `.venv` ativada, a partir da raiz do projeto):

    NETSTAT_PASTA_DADOS="$(pwd)/dados" python -m streamlit run app.py

### Persistência das configurações

Os hosts LAN, MAN e WAN, o tipo de conexão, o intervalo e o modo automático são salvos a cada alteração em `configuracao.json`, dentro da pasta de dados selecionada. Os relatórios gerados ficam na subpasta `relatorios/`.

Ao reiniciar o processo, os campos são restaurados, mas a coleta permanece parada até ser iniciada pelo usuário. A ação "Limpar Configuração" também é persistida. Arquivo ausente utiliza os valores padrão; configurações inválidas ou falhas de leitura e gravação são informadas no painel. Uma falha de gravação mantém os valores em memória durante a execução.

## Testes

A partir da raiz do projeto, com a `.venv` ativada:

    python -m unittest discover -s tests -q

Sem ativar a `.venv`, utilize:

Windows (PowerShell):

    .\.venv\Scripts\python.exe -m unittest discover -s tests -q

Linux/macOS:

    .venv/bin/python -m unittest discover -s tests -q

Os testes usam diretórios temporários para isolar os arquivos gerados dos dados de uso normal.

## Fluxo de uso típico

1. o usuário abre a aplicação em Streamlit;
2. os hosts de cada camada são preenchidos manualmente ou detectados automaticamente;
3. a coleta é iniciada em múltiplas threads;
4. as medições são gravadas em CSV;
5. gráficos e indicadores estatísticos são atualizados em tempo real.

## Mudanças de escopo e evolução do projeto

Durante a construção do projeto, alguns planos iniciais foram ajustados:

- a comparação com o modelo teórico M/M/1 foi retirada do escopo confirmado, sem definição sobre uma implementação futura;
- o painel Streamlit tornou-se parte central da solução, e não apenas uma extensão opcional — inclusive com controle completo de iniciar/parar a coleta pelo navegador, não só visualização;
- o `main.py`, ponto de entrada original via terminal, foi descontinuado: sua lógica de coleta multi-host foi absorvida pelo `app.py`, eliminando a duplicação entre os dois pontos de entrada que existiu por um período do projeto;
- a coleta foi estruturada para funcionar com múltiplos destinos simultâneos em diferentes camadas de rede (LAN/MAN/WAN), com nomeação de arquivo por rótulo de camada, host e tipo de conexão;
- a detecção automática de rede passou a ser um recurso principal, para reduzir a configuração manual;
- os histogramas de distribuição (requisito 17) e o teste de hipóteses / teste t (requisito 15) foram avaliados e **removidos definitivamente do escopo confirmado** do projeto — não estão em andamento nem previstos para retomada;
- o armazenamento permaneceu em CSV exclusivamente; o suporte alternativo em SQLite (requisito 7) foi avaliado e removido do projeto;
- o cronograma foi removido do documento de escopo, com definição posterior.

## Funcionalidades implementadas

- coleta periódica de latência via ping (req. 1, 2, 3);
- cálculo de jitter (req. 5) e da taxa de perda de pacotes (req. 4);
- suporte a múltiplos hosts simultâneos, com coleta em threads (req. 10);
- tratamento de timeouts e hosts inacessíveis sem interromper a coleta (req. 8);
- armazenamento em CSV (req. 6);
- detecção automática do gateway padrão da rede local (LAN);
- aproximação do primeiro host externo via traceroute/tracepath (MAN);
- detecção automática do tipo de conexão (Wi-Fi ou Ethernet) a partir da interface usada pela rota padrão;
- interface web com Streamlit para iniciar/parar a coleta e visualizar gráficos em tempo real (req. 19);
- estatística descritiva com média, mediana, desvio padrão e percentis (req. 11);
- identificação de outliers por IQR (req. 13) — z-score (req. 12) avaliado e removido;
- destaque visual de outliers por IQR nos gráficos de série temporal, ativável por toggle no painel (req. 18);
- correlação entre horário do dia e latência (req. 14);
- geração automatizada de relatório consolidado em Markdown (req. 20), com página exclusiva no painel para preview e exportação em Markdown, PDF e HTML;
- separação de dados por ambiente e persistência das configurações entre reinícios;
- geração de dados simulados para desenvolvimento e testes.

## Formato dos dados

Cada linha de CSV representa uma medição, com o seguinte esquema:

    timestamp,host,latencia_ms,jitter_ms,perda_pacotes_pct

O tipo de conexão não é uma coluna do CSV: ele é registrado no nome do arquivo, no formato:

    {pasta_de_dados}/{rotulo_camada}_{host}_{rotulo_sessao}.csv

Exemplo: `wan_8.8.8.8_wifi.csv`. Os rótulos de camada utilizados são `lan`, `man` e `wan`; os rótulos de sessão armazenados são `wifi` e `ethernet`, exibidos como "Wi-Fi" e "Ethernet". A coluna `tipo_conexao` é reconstruída no carregamento dos dados, a partir do sufixo do nome do arquivo.

## Relação com o conteúdo das disciplinas

| Tópico da ementa | Onde aparece no projeto |
|---|---|
| Medidas de posição e dispersão | Estatística descritiva (req. 11) |
| Distribuições de probabilidade | Não coberto — dependia da comparação com Teoria das Filas, fora do escopo confirmado |
| Correlação | Correlação entre horário do dia e latência (req. 14) |
| Testes de hipóteses (Z, t) | Ambos removidos do escopo confirmado — z-score por masking (req. 12); teste t (req. 15) não implementado |
| Tipos de rede (LAN, MAN, WAN) | Hosts organizados e detectados automaticamente por camada |
| Comandos de diagnóstico (ping, traceroute, ipconfig) | Base do coletor e da detecção automática de hosts |
| Protocolos (ICMP) | Implícito na coleta via ping |
| Análise de pacotes com Wireshark | Atividade manual complementar, não incorporada ao código |

## Decisões metodológicas

- **Outliers por IQR, sem Z-score.** O Z-score foi avaliado e removido por pressupor distribuição normal e por sofrer mascaramento: os próprios outliers inflam o desvio padrão e deixam de ser detectados. Distribuições de latência de rede são assimétricas, com cauda longa à direita, o que torna o IQR mais robusto e adequado.
- **Soluções simples primeiro.** Complexidade é adiada quando não é necessária de imediato (por exemplo, ainda não há coluna de tipo de erro no CSV).
- **Teste t removido do escopo.** A comparação estatística entre grupos (ex.: Wi-Fi vs. Ethernet) por teste t foi avaliada, mas não faz mais parte do escopo confirmado do projeto.
- **Agregação apenas na visualização.** Médias por minuto suavizam os gráficos de série temporal, mas nunca são usadas para detecção de outliers — agregar antes de detectar outliers mascararia picos reais.
- **Perda de pacotes por janela, não cumulativa.** A taxa de perda exibida nos gráficos é recalculada por janela de tempo, evitando que o contador cumulativo (que reinicia a cada execução do coletor) esconda picos de instabilidade pontuais.

## Decisões de implementação

- a coleta é desacoplada do armazenamento: o `PingCollector` utiliza callbacks;
- o ping é executado via `subprocess`, com `platform.system()` para compatibilidade entre sistemas, evitando os problemas de privilégio da biblioteca `ping3` no Windows;
- a coleta em múltiplos hosts utiliza threads, com `threading.Event` para permitir parar cada uma de forma controlada a partir da interface (necessário para o botão "Parar" do Streamlit, já que não há Ctrl+C dentro do navegador);
- a detecção de rede usa PowerShell (`Get-NetRoute`) no Windows e `ip route` no Linux para o gateway; `tracert -d` (Windows), `tracepath` (Linux) ou `traceroute` (macOS) para o primeiro salto externo. No Windows, a leitura não depende do idioma do sistema (objetos do PowerShell e linhas de salto do `tracert`, sem rótulos traduzidos); no Linux e no macOS, os comandos rodam com `LC_ALL=C`;
- a detecção do tipo de conexão cruza a rota padrão com o tipo físico da interface: no Windows, lê `PhysicalMediaType` do adaptador via PowerShell (`Native 802.11` = Wi-Fi, `802.3` = Ethernet); no Linux, extrai o dispositivo de `ip route show default` e verifica a existência de `/sys/class/net/<dev>/phy80211` (presente apenas em interfaces Wi-Fi), sem depender de `iw`/`iwconfig`. Interfaces virtuais (VPN, tethering) não são classificadas;
- a pasta legada `dados/` do projeto está no `.gitignore`; por padrão, CSVs, relatórios e configurações ficam no perfil do usuário, conforme a seção "Dados, ambientes e configurações";
- `scripts/gerar_dados_simulados.py` gera dados sintéticos para permitir o desenvolvimento sem depender do acúmulo de coletas reais.

## Estrutura do projeto

- app.py — ponto de entrada do painel Streamlit: configura a página e registra a navegação entre as demais;
- paginas/ — páginas do painel Streamlit: Monitor (coleta e visualização) e Relatório (preview e download do relatório consolidado);
- coletor/ — módulos de coleta e detecção de rede;
- armazenamento/ — persistência dos dados coletados;
- analise/ — cálculo estatístico, identificação de padrões e geração do relatório consolidado;
- visualizacao/ — gráficos e visualizações;
- dados/ — pasta legada de medições, ignorada pelo Git; pode ser selecionada explicitamente com `NETSTAT_PASTA_DADOS`;
- scripts/ — utilitários de apoio e geração de dados simulados.

Todas as pastas de código possuem `__init__.py`.

## Status atual do projeto

### Implementado

- [x] coleta periódica via ping (req. 1, 2, 3);
- [x] cálculo de jitter e perda de pacotes (req. 4, 5);
- [x] monitoramento de múltiplos destinos por camada de rede (req. 10);
- [x] tratamento de falhas e timeouts (req. 8);
- [x] armazenamento em CSV (req. 6);
- [x] detecção automática de gateway, provedor e tipo de conexão;
- [x] painel Streamlit com controle completo de iniciar/parar (req. 19);
- [x] estatísticas descritivas (req. 11);
- [x] detecção de outliers por IQR (req. 13);
- [x] correlação entre horário e latência (req. 14);
- [x] destaque visual de outliers nos gráficos de série temporal (req. 18), ativável por toggle no painel;
- [x] geração automatizada de relatório consolidado (req. 20), com exportação em Markdown, PDF e HTML;
- [x] separação de dados de desenvolvimento e produção;
- [x] persistência das configurações entre reinícios.

### Pendente

- [ ] coleta extensiva em múltiplos dias para validação real;
- [ ] comparação mais aprofundada entre Wi-Fi e Ethernet;
- [ ] refinamento das visualizações;
- [ ] captura e inspeção de tráfego com Wireshark (atividade manual, planejada para a etapa de relatório final).

### Fora do escopo confirmado

- [ ] histogramas de distribuição (req. 17) — avaliado e removido;
- [ ] teste de hipóteses / teste t (req. 15) — avaliado e removido;
- [ ] comparação com modelo teórico de Teoria das Filas (M/M/1);
- [ ] comparação de desempenho entre TCP e UDP.

## Observações importantes

- o projeto é uma ferramenta prática de diagnóstico de rede, e não substitui ferramentas especializadas de análise de rede;
- a camada MAN é uma aproximação baseada em traceroute, e não uma identificação exata do provedor;
- no Linux, o `tracepath` às vezes não obtém resposta do primeiro roteador externo, retornando o segundo salto como resultado — um comportamento observado mesmo quando `traceroute`/`tracert`, no mesmo ambiente, conseguem detectar o primeiro. É uma limitação da técnica/rede, não um erro do sistema;
- a detecção de gateway e do primeiro host externo é um recurso de apoio; o usuário pode ajustar os valores manualmente quando a detecção falha;
- taxas elevadas de outliers no gateway de hotspot móvel decorrem das características da rede móvel, e não de erros de coleta.

## Licença

[Licença MIT](LICENSE). Este projeto é destinado a fins acadêmicos e de desenvolvimento de software em contexto universitário.
