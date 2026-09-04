"""
main.py

Orquestra a coleta simultânea de latência para múltiplos hosts,
cada um rodando em sua própria thread e salvando em um arquivo CSV separado.

Cobre o requisito funcional:
10. Coletar simultaneamente múltiplos destinos, possibilitando comparar
    rede local e internet.
"""

import threading
import time

from coletor.ping_collector import PingCollector, _criar_callback_com_armazenamento
from armazenamento.armazenamento import ArmazenamentoCSV


# Hosts monitorados simultaneamente:
# - Roteador local: linha de base da rede interna (ajuste para o IP real do seu roteador)
# - 8.8.8.8 (Google DNS): referência externa principal
# - 1.1.1.1 (Cloudflare DNS): referência externa de controle
HOSTS_PARA_MONITORAR = ["172.20.10.1", "8.8.8.8", "1.1.1.1"]

INTERVALO_SEGUNDOS = 5.0


def _nome_arquivo_para_host(host: str) -> str:
    """Transforma um host (ex.: '8.8.8.8') em um nome de arquivo seguro (ex.: '8_8_8_8')."""
    return host.replace(".", "_").replace(":", "_")


def perguntar_tipo_de_conexao() -> str:
    """
    Pergunta ao usuário, via terminal, qual o tipo de conexão da sessão atual.
    Retorna 'wifi' ou 'cabo'. Repete a pergunta até receber uma resposta válida,
    para evitar rótulos inconsistentes (ex.: 'wifi' numa sessão e 'Wi-Fi' em outra)
    que fariam sessões da mesma conexão caírem em arquivos diferentes sem querer.
    """
    while True:
        resposta = input("Digite W para Wi-Fi ou C para Cabo: ").strip().upper()
        if resposta == "W":
            return "wifi"
        if resposta == "C":
            return "cabo"
        print("Opção inválida. Digite apenas W ou C.")


def iniciar_coleta_multihost(hosts: list, intervalo_segundos: float, rotulo_sessao: str):
    """
    Cria e inicia uma thread de coleta por host, cada uma salvando em
    um arquivo CSV separado dentro de dados/, identificado também pelo
    tipo de conexão (rotulo_sessao) para permitir comparação posterior
    entre Wi-Fi e cabo (requisito 15 — teste de hipóteses).
    """
    threads = []

    for host in hosts:
        coletor = PingCollector(host=host, intervalo_segundos=intervalo_segundos)

        nome_arquivo = f"dados/medicoes_{_nome_arquivo_para_host(host)}_{rotulo_sessao}.csv"
        armazenamento = ArmazenamentoCSV(caminho_arquivo=nome_arquivo)
        callback = _criar_callback_com_armazenamento(armazenamento)

        thread = threading.Thread(
            target=coletor.iniciar_coleta_continua,
            args=(callback,),
            daemon=True,  # a thread encerra automaticamente quando o programa principal termina
            name=f"coleta-{host}-{rotulo_sessao}",
        )
        threads.append(thread)
        thread.start()

    return threads


if __name__ == "__main__":
    rotulo_sessao = perguntar_tipo_de_conexao()

    print(f"Iniciando coleta simultânea para {len(HOSTS_PARA_MONITORAR)} hosts "
          f"({rotulo_sessao}): {', '.join(HOSTS_PARA_MONITORAR)}")

    threads = iniciar_coleta_multihost(HOSTS_PARA_MONITORAR, INTERVALO_SEGUNDOS, rotulo_sessao)

    try:
        # Mantém o programa principal vivo enquanto as threads coletam em segundo plano.
        # Um loop simples com sleep é usado em vez de thread.join(), pois join()
        # bloquearia esperando uma única thread terminar, e como são daemons
        # que rodam para sempre, isso funciona igual mas complicaria o Ctrl+C.
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nColeta interrompida pelo usuário.")