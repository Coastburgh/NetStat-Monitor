# Glossário de Termos — NetStat Monitor

Lista de definição dos principais termos técnicos utilizados no projeto, tanto da área de redes de computadores quanto de estatística.

## Redes de Computadores

**Latência**
Tempo decorrido entre o envio de uma solicitação a um host e o recebimento da resposta correspondente, geralmente medido em milissegundos (ms). É a métrica central coletada pelo projeto.

**Jitter**
Variação da latência entre medições consecutivas. Um jitter alto indica uma conexão instável, mesmo que a latência média esteja dentro do esperado.

**Perda de pacotes**
Percentual de pacotes enviados que não retornam ou não chegam ao destino dentro do tempo esperado, indicando problemas de conectividade.

**Ping**
Comando de diagnóstico de rede que envia pacotes ICMP a um host de destino e mede o tempo de resposta, servindo de base para a coleta de latência do projeto.

**ICMP (Internet Control Message Protocol)**
Protocolo da camada de rede utilizado para troca de mensagens de controle e diagnóstico, como as usadas pelo comando ping.

**Timeout**
Situação em que uma resposta esperada (como a de um ping) não chega dentro do tempo limite definido, sendo tratada pelo sistema sem interromper a coleta contínua.

**Host**
Qualquer dispositivo endereçável em uma rede (ex.: um servidor, roteador ou computador) que pode ser alvo de testes de conectividade.

## Estatística

**Estatística descritiva**
Conjunto de técnicas usadas para resumir e descrever as características de um conjunto de dados, como média, mediana, desvio padrão e percentis.

**Média**
Soma de todos os valores de um conjunto de dados dividida pela quantidade de valores; representa o valor "típico" central dos dados.

**Mediana**
Valor que ocupa a posição central de um conjunto de dados ordenado, menos sensível a valores extremos do que a média.

**Desvio padrão**
Medida de dispersão que indica o quanto os valores de um conjunto de dados variam em relação à média.

**Percentil**
Valor abaixo do qual se encontra uma determinada porcentagem dos dados (ex.: o percentil 90 da latência indica o valor abaixo do qual estão 90% das medições).

**Outlier**
Valor que se distancia significativamente do padrão geral dos dados, podendo indicar uma anomalia real (como um pico de latência) ou um erro de medição.

**Z-score**
Medida que indica a quantos desvios padrão um valor está distante da média do conjunto de dados. Utilizado no projeto para identificar outliers de latência.

**IQR (Intervalo Interquartil)**
Diferença entre o terceiro quartil (Q3) e o primeiro quartil (Q1) de um conjunto de dados. Método alternativo ao z-score para identificar outliers, mais robusto a distribuições assimétricas.

**Correlação**
Medida estatística que indica o grau de associação entre duas variáveis (ex.: horário do dia e latência observada), variando entre -1 e 1.

**Teste de hipóteses**
Procedimento estatístico utilizado para verificar se uma diferença observada entre dois grupos de dados é estatisticamente significativa ou pode ter ocorrido ao acaso.

**Teste t**
Tipo específico de teste de hipóteses utilizado para comparar as médias de dois grupos de dados (ex.: latência em Wi-Fi vs. latência em cabo), verificando se a diferença entre eles é estatisticamente significativa.

**Teoria das Filas**
Ramo da estatística/matemática aplicada que estuda o comportamento de sistemas de espera, como pacotes de rede aguardando processamento. O modelo M/M/1 é um dos mais simples dessa teoria (atualmente fora do escopo confirmado do projeto).

## Ferramentas

**CSV (Comma-Separated Values)**
Formato de arquivo de texto simples utilizado para armazenar dados tabulares, com valores separados por vírgulas.

**SQLite**
Sistema de banco de dados relacional leve, que armazena todo o banco em um único arquivo, sem necessidade de um servidor separado.

**Matplotlib**
Biblioteca Python utilizada para geração de gráficos, como séries temporais e histogramas.

**Streamlit**
Biblioteca Python utilizada para criar painéis (dashboards) interativos de visualização de dados com pouco código.

**Wireshark**
Software de análise de protocolos de rede utilizado para capturar e inspecionar visualmente o tráfego de pacotes, como os pacotes ICMP gerados pelo ping.
