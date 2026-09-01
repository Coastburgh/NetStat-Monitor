# NetStat Monitor

Projeto Integrador — Faculdade de Princípios Militares

**Equipe:** Eduardo F. Costa Borges, João Pedro Pereira, Fernando Ferreira Vaz, Tamynne Vitória, Paulo Henrique
**Orientador:** Leonardo A. Portes

## Descrição do Projeto

O NetStat Monitor é um projeto de software voltado à coleta e análise estatística de métricas de rede, com o objetivo de caracterizar o comportamento de uma conexão de internet ao longo do tempo e identificar padrões e anomalias de desempenho. O sistema é desenvolvido em Python e realiza coletas periódicas de latência, perda de pacotes e jitter por meio de comandos de ping, armazenando cada medição em um arquivo CSV ou em um banco de dados SQLite, sempre acompanhada de um registro de data e hora.

A coleta é planejada para ocorrer de forma contínua, em segundo plano, por vários dias e em condições variadas de uso — como redes Wi-Fi e cabeadas, em diferentes horários do dia — de modo a formar uma base de dados robusta o suficiente para sustentar uma análise estatística consistente. O tratamento de falhas comuns, como timeouts e hosts inacessíveis, é um ponto de atenção central do projeto, já que a coleta não pode ser interrompida por instabilidades momentâneas da rede.

Sobre os dados coletados, o sistema aplica técnicas de estatística descritiva (média, mediana, desvio padrão e percentis) e métodos de detecção de outliers, como z-score e intervalo interquartil (IQR), para identificar picos anômalos de latência. Também é realizada uma análise de correlação entre o horário do dia e a latência observada, além de um teste de hipóteses (teste t) para comparar estatisticamente diferentes condições de rede, como Wi-Fi contra cabo ou horário de pico contra fora de pico.

Os resultados são apresentados por meio de gráficos de série temporal e histogramas de distribuição gerados com matplotlib, com destaque visual para os outliers detectados, podendo evoluir para um painel interativo construído com Streamlit. Complementarmente, o projeto utiliza o Wireshark para capturar e inspecionar visualmente os pacotes ICMP gerados durante os testes de ping, agregando uma camada de análise qualitativa do tráfego à análise estatística quantitativa.

> **Observação:** a comparação dos dados reais com um modelo teórico de filas (M/M/1) foi retirada do escopo confirmado do projeto neste momento, permanecendo como uma possível extensão a ser avaliada pelo grupo conforme o andamento do trabalho.

O projeto se conecta diretamente aos conteúdos das disciplinas de Estatística Aplicada à Informática e Introdução a Redes de Computadores, servindo tanto como exercício prático de programação quanto como estudo aplicado de análise de dados de rede.

## Tecnologias

- **Linguagem:** Python
- **Coleta de dados:** `ping3` ou `subprocess`
- **Armazenamento:** CSV ou SQLite
- **Análise estatística:** `pandas`, `numpy`, `scipy`
- **Visualização:** `matplotlib` (e, opcionalmente, um painel com `streamlit`)
- **Inspeção de tráfego:** Wireshark

## Mapeamento com o Conteúdo das Disciplinas

### Estatística Aplicada à Informática

| Conteúdo do plano de ensino | Onde aparece no projeto |
|---|---|
| Medidas de posição e dispersão (média, mediana, desvio padrão) | Análise estatística dos dados de latência |
| Coleta e organização de dados (tabelas e gráficos) | Coleta em CSV/SQLite e visualização com matplotlib |
| Distribuições de probabilidade (Poisson, Normal) | Não coberto no momento — dependia da comparação com Teoria das Filas, atualmente fora do escopo confirmado |
| Correlação | Correlação entre horário do dia e latência |
| Testes de hipóteses (Z, t) | Comparação estatística entre condições de rede (teste t) |

### Introdução a Redes de Computadores

| Conteúdo do plano de ensino | Onde aparece no projeto |
|---|---|
| Comandos de diagnóstico (ping, traceroute, ipconfig) | Base do coletor de dados |
| Camadas de transporte (TCP/UDP) | Extensão opcional — comparação de desempenho entre TCP e UDP |
| Análise de pacotes com Wireshark | Captura e inspeção do tráfego ICMP gerado pelo ping |
| Protocolos (ICMP) | Implícito na coleta, citado explicitamente no relatório final |

## Status

Projeto em fase inicial de desenvolvimento — Etapa 02 (Descrição da Ideia + Persona + Requisitos Funcionais) concluída e entregue.
