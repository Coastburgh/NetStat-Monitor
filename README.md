# NetStat Monitor

[English version](README_EN.md)

Projeto Integrador — Faculdade de Princípios Militares

Equipe: Eduardo Costa Borges, João P. Pereira, Fernando Ferreira Vaz, Tamynne Vitória, Paulo Henrique e Cid Mendes
Professor: Leonardo A. Porte## Visão geral

O NetStat Monitor é uma ferramenta para monitorar e analisar métricas de rede em tempo real, com foco em latência, jitter, perda de pacotes e comportamento de acesso à internet. O projeto coleta dados por ping em intervalos configuráveis, salva as medições em arquivos CSV e apresenta os resultados em um painel interativo em Streamlit.

A documentação do projeto está disponível em português neste arquivo e em inglês em [README_EN.md](README_EN.md).

A ideia central do projeto é permitir que uma mesma sessão de coleta compare diferentes camadas de rede — LAN, MAN e WAN — com uma interface simples e sem depender de configuração manual de IPs em todos os casos. Para isso, o sistema também inclui detecção automática de gateway e do primeiro host externo do provedor.

## Mudanças de escopo e evolução do projeto

Durante a construção do projeto, alguns planos iniciais foram ajustados:

- a comparação com o modelo teórico M/M/1 foi retirada do escopo confirmado;
- o painel Streamlit tornou-se parte central da solução, e não apenas uma extensão opcional;
- a coleta foi estruturada para funcionar com múltiplos destinos simultaneamente em diferentes camadas de rede;
- a detecção automática de rede passou a ser um recurso principal do sistema, especialmente para reduzir a necessidade de configuração manual.

Esses ajustes mantiveram a proposta principal do projeto, mas deixaram a solução mais prática, observável e útil para análise de desempenho real de rede.

## Funcionalidades implementadas

- coleta periódica de latência via ping;
- cálculo de jitter e taxa de perda de pacotes acumulada;
- suporte a múltiplos hosts simultâneos;
- armazenamento em CSV e estrutura pronta para extensões em SQLite;
- detecção automática do gateway padrão da rede local;
- aproximação do primeiro host externo via traceroute;
- interface web com Streamlit para iniciar/parar coleta e visualizar gráficos em tempo real;
- análise estatística descritiva com média, mediana, desvio padrão e percentis;
- identificação de outliers por IQR;
- correlação entre horário do dia e latência.

## Estrutura do projeto

- app.py — painel principal em Streamlit;
- coletor/ — módulos de coleta e detecção de rede;
- armazenamento/ — persistência dos dados coletados;
- analise/ — cálculo estatístico e identificação de padrões;
- visualizacao/ — gráficos e visualizações;
- dados/ — arquivos CSV gerados pelas coletas;
- scripts/ — utilitários de apoio e geração de dados simulados.

## Requisitos

- Python 3.10 ou superior;
- pip;
- ambiente virtual recomendado.

Dependências principais:

- streamlit
- pandas
- numpy
- scipy
- plotly
- matplotlib

O arquivo requirements.txt contém a lista completa das dependências do projeto.

## Instalação

1. Clone o repositório:

   git clone <url-do-repositorio>

2. Entre na pasta do projeto:

   cd NetStat-Monitor

3. Crie e ative um ambiente virtual:

   python -m venv venv
   .\venv\Scripts\Activate.ps1

4. Instale as dependências:

   pip install -r requirements.txt

## Execução

### Painel Streamlit

Para iniciar a interface do projeto:

   streamlit run app.py

Na interface, você pode:

- informar os hosts das camadas LAN, MAN e WAN;
- detectar automaticamente o gateway e o primeiro host externo;
- iniciar e interromper uma coleta;
- visualizar gráficos de latência, jitter e perda de pacotes.

### Detecção automática de rede

Para testar apenas a detecção de hosts das camadas de rede:

   python -m coletor.deteccao_rede

### Coleta direta

O módulo de coleta também pode ser executado diretamente para testes rápidos:

   python -m coletor.ping_collector

## Fluxo de uso típico

1. o usuário abre a aplicação em Streamlit;
2. o sistema permite preencher os hosts de cada camada ou detectar automaticamente;
3. a coleta se inicia em múltiplas threads;
4. as medições são gravadas em CSV;
5. gráficos e indicadores estatísticos são atualizados em tempo real.

## Status atual do projeto

### Implementado

- [x] coleta periódica via ping;
- [x] monitoramento de múltiplos destinos;
- [x] tratamento de falhas e timeouts;
- [x] armazenamento em CSV;
- [x] detecção automática de gateway e provedor;
- [x] painel Streamlit;
- [x] estatísticas descritivas;
- [x] detecção de outliers por IQR;
- [x] correlação entre horário e latência;
- [x] estrutura de visualização com gráficos.

### Ainda pendente ou em abertura

- [ ] geração automatizada de relatório consolidado;
- [ ] coleta extensiva em múltiplos dias para validação real;
- [ ] comparações mais aprofundadas entre Wi-Fi e cabo;
- [ ] refinamento de visualizações e exportação de relatórios.

## Observações importantes

- o projeto foi pensado como ferramenta prática de diagnóstico de rede, e não como um substituto de ferramentas de análise de rede especialistas;
- a camada MAN é tratada como uma aproximação baseada em traceroute, e não como identificação exata do provedor;
- a detecção de gateway e primeiro host externo é útil como suporte, mas o usuário sempre pode ajustar manualmente os valores da coleta.

## Licença

Este projeto é destinado a fins acadêmicos e de desenvolvimento de software em contexto universitário.
