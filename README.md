# NetStat Monitor

[English version](README_EN.md)

Projeto Integrador 2026/2 — Faculdade de Princípios Militares

Equipe: Eduardo Costa Borges, Cid Mendes, João P. Pereira, Fernando Ferreira Vaz, Tamynne Vitória e Paulo Carrijo
Professor: Leonardo A. Portes

## Visão geral

O NetStat Monitor é uma ferramenta para monitorar e analisar métricas de rede em tempo real, com foco em latência, jitter, perda de pacotes e comportamento de acesso à internet. O projeto coleta dados por ping em intervalos configuráveis, salva as medições em arquivos CSV e aplica análise estatística para caracterizar o comportamento da rede e identificar anomalias. Os resultados são apresentados em um painel interativo em Streamlit.

A documentação do projeto está disponível em português neste arquivo e em inglês em [README_EN.md](README_EN.md).

A ideia central é permitir que uma mesma sessão de coleta compare diferentes camadas de rede (LAN, MAN e WAN) sem depender de configuração manual de IPs em todos os casos. Para isso, o sistema inclui detecção automática do gateway e do primeiro host externo do provedor. Essa organização por camadas conecta o projeto diretamente ao tópico "Tipos de redes (LAN, MAN, WAN)" da ementa de Introdução a Redes de Computadores.

## Mudanças de escopo e evolução do projeto

Durante a construção do projeto, alguns planos iniciais foram ajustados:

- a comparação com o modelo teórico M/M/1 foi retirada do escopo confirmado, sem definição sobre uma implementação futura;
- o painel Streamlit tornou-se parte central da solução, e não apenas uma extensão opcional — inclusive com controle completo de iniciar/parar a coleta pelo navegador, não só visualização;
- o `main.py`, ponto de entrada original via terminal, foi descontinuado: sua lógica de coleta multi-host foi absorvida pelo `app.py`, eliminando a duplicação entre os dois pontos de entrada que existiu por um período do projeto;
- a coleta foi estruturada para funcionar com múltiplos destinos simultâneos em diferentes camadas de rede (LAN/MAN/WAN), com nomeação de arquivo por rótulo de camada em vez de por IP;
- a detecção automática de rede passou a ser um recurso principal, para reduzir a configuração manual;
- os histogramas de distribuição (requisito 17) e o teste de hipóteses / teste t (requisito 15) foram avaliados e **removidos definitivamente do escopo confirmado** do projeto — não estão em andamento nem previstos para retomada;
- o armazenamento principal permaneceu em CSV; o suporte alternativo em SQLite (requisito 7) foi implementado e testado como módulo (`ArmazenamentoSQLite`), mas não está em uso na pipeline ativa do `app.py`, que utiliza CSV exclusivamente;
- o cronograma foi removido do documento de escopo, com definição posterior.

## Funcionalidades implementadas

- coleta periódica de latência via ping (req. 1, 2, 3);
- cálculo de jitter (req. 5) e da taxa de perda de pacotes (req. 4);
- suporte a múltiplos hosts simultâneos, com coleta em threads (req. 10);
- tratamento de timeouts e hosts inacessíveis sem interromper a coleta (req. 8);
- armazenamento em CSV (req. 6); suporte alternativo em SQLite implementado, mas não utilizado na pipeline ativa (req. 7);
- detecção automática do gateway padrão da rede local (LAN);
- aproximação do primeiro host externo via traceroute/tracepath (MAN);
- interface web com Streamlit para iniciar/parar a coleta e visualizar gráficos em tempo real (req. 19);
- estatística descritiva com média, mediana, desvio padrão e percentis (req. 11);
- identificação de outliers por IQR (req. 13) — z-score (req. 12) avaliado e removido;
- correlação entre horário do dia e latência (req. 14);
- geração de dados simulados para desenvolvimento e testes.

## Formato dos dados

Cada linha de CSV representa uma medição, com o seguinte esquema:

    timestamp,host,latencia_ms,jitter_ms,perda_pacotes_pct

O tipo de conexão não é uma coluna do CSV: ele é registrado no nome do arquivo, no formato:

    dados/medicoes_{rotulo_camada}_{rotulo_sessao}.csv

Exemplo: `medicoes_lan_gateway_wifi.csv`. Os rótulos de camada utilizados são `lan_gateway`, `man_provedor` e `wan_google`; os rótulos de sessão armazenados são `wifi` e `cabo`, exibidos como "Wi-Fi" e "Cabo". A coluna `tipo_conexao` é reconstruída no carregamento dos dados, a partir do sufixo do nome do arquivo.

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
- **Teste t removido do escopo.** A comparação estatística entre grupos (ex.: Wi-Fi vs. cabo) por teste t foi avaliada, mas não faz mais parte do escopo confirmado do projeto.
- **Agregação apenas na visualização.** Médias por minuto suavizam os gráficos de série temporal, mas nunca são usadas para detecção de outliers — agregar antes de detectar outliers mascararia picos reais.
- **Perda de pacotes por janela, não cumulativa.** A taxa de perda exibida nos gráficos é recalculada por janela de tempo, evitando que o contador cumulativo (que reinicia a cada execução do coletor) esconda picos de instabilidade pontuais.

## Decisões de implementação

- a coleta é desacoplada do armazenamento: o `PingCollector` utiliza callbacks;
- o ping é executado via `subprocess`, com `platform.system()` para compatibilidade entre sistemas, evitando os problemas de privilégio da biblioteca `ping3` no Windows;
- a coleta em múltiplos hosts utiliza threads, com `threading.Event` para permitir parar cada uma de forma controlada a partir da interface (necessário para o botão "Parar" do Streamlit, já que não há Ctrl+C dentro do navegador);
- a detecção de rede usa `ipconfig`/PowerShell no Windows e `ip route` no Linux para o gateway; `tracert` (Windows), `tracepath` (Linux) ou `traceroute` (macOS) para o primeiro salto externo;
- a pasta `dados/` está no `.gitignore`, o que inclui CSVs reais e simulados;
- `scripts/gerar_dados_simulados.py` gera dados sintéticos para permitir o desenvolvimento sem depender do acúmulo de coletas reais.

## Estrutura do projeto

- app.py — painel principal em Streamlit, único ponto de entrada da aplicação;
- coletor/ — módulos de coleta e detecção de rede;
- armazenamento/ — persistência dos dados coletados;
- analise/ — cálculo estatístico e identificação de padrões;
- visualizacao/ — gráficos e visualizações;
- dados/ — arquivos CSV gerados pelas coletas (ignorado pelo Git);
- scripts/ — utilitários de apoio e geração de dados simulados.

Todas as pastas de código possuem `__init__.py`.

## Requisitos

- Python 3.10 ou superior;
- pip;
- ambiente virtual recomendado.

Dependências principais: streamlit, pandas, numpy, scipy e plotly. O arquivo `requirements.txt` contém a lista completa.

## Instalação

1. Clone o repositório:

       git clone https://github.com/Coastburgh/NetStat-Monitor.git

2. Entre na pasta do projeto:

       cd NetStat-Monitor

3. Crie e ative um ambiente virtual:

   Windows (PowerShell):

       python -m venv venv
       .\venv\Scripts\Activate.ps1

   Caso a execução de scripts esteja bloqueada, execute uma vez:

       Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

   Como alternativa, utilize o `cmd.exe` com `venv\Scripts\activate.bat`.

   Linux/macOS:

       python -m venv venv
       source venv/bin/activate

4. Instale as dependências:

       pip install -r requirements.txt

## Execução

### Painel Streamlit

    streamlit run app.py

Na interface, é possível:

- informar os hosts das camadas LAN, MAN e WAN;
- detectar automaticamente o gateway e o primeiro host externo;
- iniciar e interromper uma coleta;
- visualizar gráficos de latência, jitter e perda de pacotes, além da latência instantânea da última leitura.

### Detecção automática de rede

Para testar apenas a detecção de hosts das camadas de rede:

    python -m coletor.deteccao_rede

### Coleta direta

Para testes rápidos do módulo de coleta:

    python -m coletor.ping_collector

## Fluxo de uso típico

1. o usuário abre a aplicação em Streamlit;
2. os hosts de cada camada são preenchidos manualmente ou detectados automaticamente;
3. a coleta é iniciada em múltiplas threads;
4. as medições são gravadas em CSV;
5. gráficos e indicadores estatísticos são atualizados em tempo real.

## Status atual do projeto

### Implementado

- [x] coleta periódica via ping (req. 1, 2, 3);
- [x] cálculo de jitter e perda de pacotes (req. 4, 5);
- [x] monitoramento de múltiplos destinos por camada de rede (req. 10);
- [x] tratamento de falhas e timeouts (req. 8);
- [x] armazenamento em CSV (req. 6); suporte SQLite implementado, não utilizado na pipeline ativa (req. 7);
- [x] detecção automática de gateway e provedor;
- [x] painel Streamlit com controle completo de iniciar/parar (req. 19);
- [x] estatísticas descritivas (req. 11);
- [x] detecção de outliers por IQR (req. 13);
- [x] correlação entre horário e latência (req. 14).

### Pendente

- [ ] destaque visual de outliers diretamente nos gráficos de série temporal (req. 18);
- [ ] geração automatizada de relatório consolidado (req. 20);
- [ ] coleta extensiva em múltiplos dias para validação real;
- [ ] comparação mais aprofundada entre Wi-Fi e cabo;
- [ ] refinamento das visualizações e exportação de relatórios;
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

Este projeto é destinado a fins acadêmicos e de desenvolvimento de software em contexto universitário.
