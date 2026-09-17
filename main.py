"""
main.py

Orquesta a coleta simultânea de latência para os hosts representativos de
cada camada de rede (LAN, MAN, WAN), cada um rodando em sua própria thread
e salvando em um arquivo CSV separado, nomeado pelo rótulo da camada.

Cobre o requisito funcional:
10. Coletar simultaneamente múltiplos destinos, possibilitando comparar
    rede local e internet.
"""

import threading
import time

from coletor.ping_collector import PingCollector, _criar_callback_com_armazenamento
from coletor.deteccao_rede import detectar_hosts_camadas
from armazenamento.armazenamento import ArmazenamentoCSV

INTERVALO_SEGUNDOS = 5.0


def perguntar_tipo_de_conexao() -> str:
    """
    Pergunta ao usuário, via terminal, qual o tipo de conexão da sessão atual.
    Retorna 'wifi' ou 'cabo'. Repete a pergunta até receber uma resposta válida,
    para evitar rótulos inconsistentes que fariam sessões da mesma conexão
    caírem em arquivos diferentes sem querer.
    """
    while True:
        resposta = input("Digite W para Wi-Fi ou C para Cabo: ").strip().upper()
        if resposta == "W":
            return "wifi"
        if resposta == "C":
            return "cabo"
        print("Opção inválida. Digite apenas W ou C.")


def resolver_hosts_camadas() -> dict:
    """
    Detecta automaticamente os hosts de LAN, MAN e WAN, e permite ao
    usuário preencher manualmente qualquer camada que não tenha sido
    detectada (a detecção é um atalho, nunca uma dependência obrigatória).
    """
    print("Detectando hosts (gateway + primeiro salto externo)...")
    hosts_rotulados = detectar_hosts_camadas()

    for rotulo, host in list(hosts_rotulados.items()):
        if host:
            print(f"  {rotulo}: {host}")
        else:
            valor = input(
                f"  {rotulo}: não detectado. Digite manualmente (ou Enter para pular): "
            ).strip()
            if valor:
                hosts_rotulados[rotulo] = valor
            else:
                del hosts_rotulados[rotulo]

    return hosts_rotulados


def iniciar_coleta_multihost(hosts_rotulados: dict, intervalo_segundos: float, rotulo_sessao: str):
    """
    Cria e inicia uma thread de coleta por host, cada uma salvando em um
    arquivo CSV separado dentro de dados/, nomeado pelo rótulo da camada
    (lan_gateway, man_provedor, wan_google) e pelo tipo de conexão.
    """
    threads = []

    for rotulo, host in hosts_rotulados.items():
        coletor = PingCollector(host=host, intervalo_segundos=intervalo_segundos)

        nome_arquivo = f"dados/medicoes_{rotulo}_{rotulo_sessao}.csv"
        armazenamento = ArmazenamentoCSV(caminho_arquivo=nome_arquivo)
        callback = _criar_callback_com_armazenamento(armazenamento)

        thread = threading.Thread(
            target=coletor.iniciar_coleta_continua,
            args=(callback,),
            daemon=True,
            name=f"coleta-{rotulo}",
        )
        threads.append(thread)
        thread.start()

    return threads


if __name__ == "__main__":
    rotulo_sessao = perguntar_tipo_de_conexao()
    hosts_rotulados = resolver_hosts_camadas()

    if not hosts_rotulados:
        print("Nenhum host disponível para monitorar. Encerrando.")
    else:
        print(f"\nIniciando coleta simultânea ({rotulo_sessao}): "
              f"{', '.join(f'{r}={h}' for r, h in hosts_rotulados.items())}")

        threads = iniciar_coleta_multihost(hosts_rotulados, INTERVALO_SEGUNDOS, rotulo_sessao)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nColeta interrompida pelo usuário.")