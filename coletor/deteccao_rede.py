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


def _extrair_ip_v4(texto: str) -> str | None:
    """Extrai o primeiro IPv4 válido de um texto, preferindo endereços de gateway."""
    if not texto:
        return None

    # Prioriza linhas que mencionam gateway, que normalmente contêm o valor real da rota padrão.
    for linha in texto.splitlines():
        if "default gateway" in linha.lower() or "gateway padrão" in linha.lower() or "gateway" in linha.lower():
            match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", linha)
            if match:
                ip = match.group(1)
                try:
                    ipaddress.ip_address(ip)
                    if ip.startswith("127."):
                        continue
                    return ip
                except ValueError:
                    continue

    # Fallback geral: tenta capturar o primeiro IPv4 válido de qualquer parte do texto.
    for match in re.finditer(r"(\d{1,3}(?:\.\d{1,3}){3})", texto):
        ip = match.group(1)
        try:
            ipaddress.ip_address(ip)
            if not ip.startswith("127."):
                return ip
        except ValueError:
            continue

    return None


def detectar_gateway() -> str:
    """
    Retorna o IP do gateway padrão (roteador) da rede atual, lendo a
    configuração de rede do próprio sistema operacional.
    Retorna None se não conseguir detectar.
    """
    sistema = platform.system()

    try:
        if sistema == "Windows":
            # Usa a rota IPv4 padrão diretamente, que é mais robusta do que
            # o 'ipconfig' quando a interface só expõe IPv6 ou o valor está em branco.
            powershell_cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' | Select-Object -ExpandProperty NextHop -First 1).ToString()",
            ]
            resultado = subprocess.run(powershell_cmd, capture_output=True, text=True, timeout=10)
            gateway = (resultado.stdout or "").strip()
            if gateway and gateway != "On-link":
                return gateway

            resultado = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=5)
            gateway = _extrair_ip_v4(resultado.stdout)
            if gateway:
                return gateway
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


def _eh_ip_privado(ip: str) -> bool:
    """True se o IP pertence a uma faixa privada/reservada (não roteável na internet)."""
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return True  # não é um IP válido; trata como "não conta"


def _extrair_primeiro_ip_publico(texto: str, destino: str | None = "8.8.8.8") -> str | None:
    """Retorna o primeiro IP público real encontrado em um traceroute/traceroute-like."""
    destino_normalizado = destino or ""
    for linha in texto.splitlines():
        ips = re.findall(r"\d{1,3}(?:\.\d{1,3}){3}", linha)
        for ip in ips:
            if destino_normalizado and ip == destino_normalizado:
                continue
            if _eh_ip_privado(ip):
                continue
            return ip
    return None


def detectar_primeiro_host_externo(destino: str = "8.8.8.8", max_saltos: int = 6) -> str:
    """
    Executa um traceroute até 'destino' e retorna o IP do primeiro salto
    já fora da rede local (o primeiro IP público no caminho) — tipicamente
    o primeiro equipamento do provedor de internet, usado como aproximação
    da camada MAN.

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
            comando = ["tracepath", "-m", str(max_saltos), "-l", "28", destino]
        else:  # Darwin (macOS)
            comando = ["traceroute", "-m", str(max_saltos), "-w", "1", destino]

        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=30)
    except Exception as erro:
        print(f"Aviso: falha ao executar traceroute/tracepath — {type(erro).__name__}: {erro}")
        return None

    return _extrair_primeiro_ip_publico(resultado.stdout, destino=destino)


def detectar_hosts_camadas(destino_wan: str = "8.8.8.8") -> dict:
    """
    Detecta um host representativo de cada camada de rede (LAN, MAN, WAN),
    retornando um dicionário {rotulo: host} pronto para popular a lista de
    hosts monitorados com significado explícito, em vez de IPs soltos.

    - lan_gateway: o roteador da rede local (via detectar_gateway)
    - man_provedor: o primeiro salto público no caminho até destino_wan,
      uma APROXIMAÇÃO da infraestrutura do provedor — pode vir como None
    - wan_google: o destino externo fixo, fornecido diretamente

    Um valor None significa que a interface deve permitir preenchimento
    manual — a detecção é um atalho, nunca uma dependência obrigatória.
    """
    gateway = detectar_gateway()
    primeiro_externo = detectar_primeiro_host_externo(destino=destino_wan)

    return {
        "lan_gateway": gateway,
        "man_provedor": primeiro_externo,
        "wan_destino": destino_wan,
    }


if __name__ == "__main__":
    # Execução manual para teste rápido: python -m coletor.deteccao_rede
    hosts = detectar_hosts_camadas()
    for rotulo, host in hosts.items():
        print(f"{rotulo}: {host if host else '(não detectado — preencher manualmente)'}")