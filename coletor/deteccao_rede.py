"""
coletor/deteccao_rede.py

Utilitários para auto-detectar hosts representativos de cada camada de
rede (LAN, MAN, WAN), evitando que o usuário precise descobrir e digitar
esses endereços manualmente.
"""

import subprocess
import platform
import re
import ipaddress


def detectar_gateway() -> str:
    """
    Retorna o IP do gateway padrão (roteador) da rede atual, lendo a
    configuração de rede do próprio sistema operacional.
    Retorna None se não conseguir detectar.
    """
    sistema = platform.system()

    try:
        if sistema == "Windows":
            resultado = subprocess.run(
                ["ipconfig"], capture_output=True, text=True, timeout=5
            )
            for linha in resultado.stdout.splitlines():
                if "Default Gateway" in linha or "Gateway Padrão" in linha:
                    match = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", linha)
                    if match:
                        return match.group(1)
        else:
            resultado = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True, timeout=5,
            )
            match = re.search(r"default via (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", resultado.stdout)
            if match:
                return match.group(1)
    except Exception as erro:
        print(f"Aviso: falha ao detectar gateway — {type(erro).__name__}: {erro}")

    return None


def _extrair_ips_da_linha(linha: str) -> list:
    """
    Extrai possíveis IPv4 de uma linha de traceroute/tracepath, cobrindo
    dois formatos:
    1. IP puro: '192.168.1.1'
    2. IP codificado em hostname de DNS reverso, com hífens no lugar de
       pontos — prática comum de provedores brasileiros, ex.:
       '177-107-178-45.brcentral.net.br' representa 177.107.178.45.
       Sem isso, esses saltos são invisíveis para a detecção, mesmo
       quando são exatamente o salto público que procuramos.
    """
    candidatos = re.findall(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", linha)

    for match in re.finditer(r"\b(\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3})\b", linha):
        candidatos.append(match.group(1).replace("-", "."))

    return candidatos


def _eh_ip_publico(ip: str) -> bool:
    """
    True apenas se o IP é genuinamente roteável na internet pública.

    Usa is_global em vez de checar apenas 'not is_private': o atributo
    is_private do Python segue estritamente a RFC 1918 (10.x, 172.16-31.x,
    192.168.x) e NÃO reconhece a faixa 100.64.0.0/10 (CGNAT, RFC 6598),
    usada internamente por operadoras e redes corporativas grandes para
    NAT em larga escala. Um IP nessa faixa não é 'privado' pela definição
    estrita, mas também não é público de verdade — is_global cobre os
    dois casos corretamente.
    """
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False  # não é um IP válido; não conta como público


def detectar_primeiro_host_externo(destino: str = "8.8.8.8", max_saltos: int = 6) -> str:
    """
    Executa um traceroute até 'destino' e retorna o IP do primeiro salto
    já fora da rede local (o primeiro IP genuinamente público no caminho)
    — tipicamente o primeiro equipamento do provedor de internet, usado
    como aproximação da camada MAN.

    Em redes corporativas ou universitárias com vários estágios de
    infraestrutura interna (incluindo CGNAT), o IP público real pode
    aparecer bem mais tarde no caminho do que em uma rede doméstica
    simples. Se isso ultrapassar max_saltos, a detecção retorna None —
    aumentar max_saltos pode ajudar nesses casos.

    Pode retornar None mesmo em redes normais: alguns provedores não
    respondem a pacotes de saltos intermediários, o que é uma limitação
    da técnica, não um erro do código.

    Usa 'tracert' no Windows e 'tracepath' no Linux — ambos nativos do
    sistema operacional (tracepath faz parte do mesmo pacote iproute2 que
    já fornece o 'ip route' usado em detectar_gateway, então não exige
    nenhuma instalação extra). No macOS, usa 'traceroute', que também já
    vem pré-instalado por padrão.
    """
    sistema = platform.system()

    try:
        if sistema == "Windows":
            comando = ["tracert", "-h", str(max_saltos), "-w", "1000", destino]
        elif sistema == "Linux":
            comando = ["tracepath", "-m", str(max_saltos), destino]
        else:  # Darwin (macOS)
            comando = ["traceroute", "-m", str(max_saltos), "-w", "1", destino]

        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=30)
    except Exception as erro:
        print(f"Aviso: falha ao executar traceroute/tracepath — {type(erro).__name__}: {erro}")
        return None

    for linha in resultado.stdout.splitlines():
        for ip in _extrair_ips_da_linha(linha):
            if _eh_ip_publico(ip):
                return ip

    return None


def detectar_hosts_camadas(destino_wan: str = "8.8.8.8") -> dict:
    """
    Detecta um host representativo de cada camada de rede (LAN, MAN, WAN),
    retornando um dicionário {rotulo: host} pronto para popular a lista de
    hosts monitorados com significado explícito, em vez de IPs soltos.

    - lan_gateway: o roteador da rede local (via detectar_gateway)
    - man_provedor: o primeiro salto genuinamente público no caminho até
      destino_wan, uma APROXIMAÇÃO da infraestrutura do provedor — pode
      vir como None
    - wan_google: o destino externo fixo, fornecido diretamente

    Um valor None significa que a interface deve permitir preenchimento
    manual — a detecção é um atalho, nunca uma dependência obrigatória.
    """
    gateway = detectar_gateway()
    primeiro_externo = detectar_primeiro_host_externo(destino=destino_wan) if gateway else None

    return {
        "lan_gateway": gateway,
        "man_provedor": primeiro_externo,
        "wan_google": destino_wan,
    }


if __name__ == "__main__":
    # Execução manual para teste rápido: python -m coletor.deteccao_rede
    hosts = detectar_hosts_camadas()
    for rotulo, host in hosts.items():
        print(f"{rotulo}: {host if host else '(não detectado — preencher manualmente)'}")