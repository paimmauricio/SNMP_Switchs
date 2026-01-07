###################################################################################################################
#Nome do Script		:  scan_switchs.py
#Descrição		    :  Fazer coorelação de porta de switchs e tipos de equipamentos
#Autor       		:  Maurício Paim
#Email         		:  paim.mauricio@gmail.com
#Data         		:  05/01/2026
#UPDATE         	:  07/01/2026
###################################################################################################################

import sys
import time
import requests
import datetime
import os

# --- IMPORTAÇÃO DE BIBLIOTECAS ---
try:
    from pysnmp.hlapi import *
except ImportError:
    try:
        from pysnmp.hlapi.asyncore.sync import *
    except ImportError:
        print("Erro: Instale as dependências: pip install pysnmp requests")
        sys.exit(1)

# --- OIDs ---
OID_IFNAME = '1.3.6.1.2.1.31.1.1.1.1'
OID_QBRIDGE_MAC = '1.3.6.1.2.1.17.7.1.2.2.1.2' # HPE 1920S / Linux Switches
OID_STD_BRIDGE_MAC = '1.3.6.1.2.1.17.4.3.1.1'   # Switches Genéricos
OID_ARP_TABLE = '1.3.6.1.2.1.4.22.1.2'

# --- CONFIGURAÇÕES E CACHE ---
oui_cache = {}

def estimar_tipo_equipamento(vendor):
    v = vendor.lower()
    if "toshiba" in v or "tgcs" in v: return "PDV"
    if "zebra" in v or "motorola" in v or "symbol" in v: return "Coletor/Impressora"
    if "espressif" in v: return "Sensor/IoT"
    if any(x in v for x in ["apple", "samsung", "xiaomi", "motorola"]): return "Mobile/Tablet"
    if any(x in v for x in ["hikvision", "dahua", "intelbras", "axis", "vivotek"]): return "Câmera"
    if any(x in v for x in ["intel", "dell", "hp", "lenovo", "asus", "acer"]): return "PC/Notebook"
    if any(x in v for x in ["cisco", "ubiquiti", "aruba", "tp-link", "mikrotik", "datacom"]): return "Rede/Wifi"
    if "epson" in v or "bematech" in v or "elgin" in v: return "Impressora Fiscal"
    return "Outros"

def get_vendor_online(mac_address):
    oui = mac_address[:8].upper()
    if oui in oui_cache: return oui_cache[oui]
    try:
        url = f"https://api.macvendors.com/{mac_address}"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            vendor = response.text.strip()
            oui_cache[oui] = vendor
            time.sleep(1.2) # Respeitar rate limit da API
            return vendor
    except: pass
    return "Desconhecido"

# --- FUNÇÕES SNMP CORE ---

def snmp_walk_generic(ip, community, oid):
    """Função auxiliar genérica para SNMP Walk"""
    results = []
    try:
        iterator = nextCmd(SnmpEngine(), CommunityData(community, mpModel=1),
                           UdpTransportTarget((ip, 161), timeout=3, retries=1),
                           ContextData(), ObjectType(ObjectIdentity(oid)),
                           lexicographicMode=False, ignoreNonIncreasingOid=True)

        for errorIndication, errorStatus, errorIndex, varBinds in iterator:
            if not errorIndication and not errorStatus:
                for varBind in varBinds:
                    results.append((str(varBind[0]), str(varBind[1])))
    except Exception as e:
        # Silencioso para não sujar o log, erros reais aparecem na lógica principal
        pass
    return results

def get_interfaces_map(ip, community):
    """Retorna dicionário {index: nome_da_porta}"""
    print("    [Info] Mapeando nomes das interfaces...")
    if_map = {}
    # Tenta pegar ifName (mais descritivo: GE1/0/1)
    data = snmp_walk_generic(ip, community, OID_IFNAME)

    if not data:
        # Fallback para ifDescr se ifName falhar
        data = snmp_walk_generic(ip, community, '1.3.6.1.2.1.2.2.1.2')

    for oid, val in data:
        idx = oid.split('.')[-1]
        if_map[idx] = val

    return if_map

def get_arp_table(switch_ip, comunidade):
    """Retorna dicionário {mac: ip}"""
    print("    [Info] Baixando tabela ARP...")
    arp_map = {}
    data = snmp_walk_generic(switch_ip, comunidade, OID_ARP_TABLE)

    for oid, val in data:
        try:
            # OID ARP: ...22.1.2.{IfIndex}.{IP1}.{IP2}.{IP3}.{IP4} = MAC_HEX
            # O valor 'val' vem como Hex String ou bytes, precisamos tratar
            if val.startswith('0x'):
                hex_str = val.replace('0x', '')
            else:
                # Caso venha cru, tentamos converter (depende da lib)
                # Assumindo que a lib já retorna string legível ou hex
                hex_str = val.replace('-', '').replace(':', '')

            # Formata MAC
            if len(hex_str) >= 12:
                mac_clean = ":".join([hex_str[i:i+2] for i in range(0, 12, 2)]).upper()
            else:
                continue

            # Extrai IP da OID
            ip_parts = oid.split('.')[-4:]
            ip_addr = ".".join(ip_parts)

            arp_map[mac_clean] = ip_addr
        except: continue
    return arp_map

def get_mac_address_hex(decimal_list):
    """Converte lista de decimais para MAC formatado"""
    return ":".join([f"{int(x):02X}" for x in decimal_list])

# --- ESTRATÉGIAS DE LEITURA MAC ---

def strategy_qbridge(ip, community, iface_map):
    """Estratégia para HPE 1920S e Linux Switches"""
    data = snmp_walk_generic(ip, community, OID_QBRIDGE_MAC)
    results = []
    for oid, port_idx in data:
        try:
            # Parse OID: ...17.7.1.2.2.1.2.{VLAN}.{MAC_DECIMALS...}
            parts = oid.split('.')
            mac_decimals = parts[-6:]
            vlan_id = parts[-7] # Extrai VLAN
            mac_addr = get_mac_address_hex(mac_decimals)

            # Traduz Index para Nome
            port_name = iface_map.get(port_idx, f"Index {port_idx}")

            results.append({
                'port_raw': int(port_idx) if port_idx.isdigit() else 9999,
                'port_name': port_name,
                'mac': mac_addr,
                'vlan': vlan_id,
                'source': 'Q-BRIDGE'
            })
        except: continue
    return results

def strategy_standard(ip, community, iface_map):
    """Estratégia Padrão (Bridge MIB)"""
    data = snmp_walk_generic(ip, community, OID_STD_BRIDGE_MAC)
    results = []
    for oid, port_idx in data:
        try:
            # Parse OID: ...17.4.3.1.1.{MAC_DECIMALS...}
            parts = oid.split('.')
            mac_decimals = parts[-6:]
            mac_addr = get_mac_address_hex(mac_decimals)

            port_name = iface_map.get(port_idx, f"Index {port_idx}")

            results.append({
                'port_raw': int(port_idx) if port_idx.isdigit() else 9999,
                'port_name': port_name,
                'mac': mac_addr,
                'vlan': '?',
                'source': 'STD-BRIDGE'
            })
        except: continue
    return results

def get_mac_table_unified(switch_ip, comunidade):
    print(f"\n[...] Iniciando varredura em {switch_ip}...")

    # 1. Obter Mapas Auxiliares
    tabela_arp = get_arp_table(switch_ip, comunidade)
    tabela_portas = get_interfaces_map(switch_ip, comunidade)

    # 2. Tentar Ler MACs (Hierarquia de Estratégias)

    # Tentativa A: Q-BRIDGE (Ideal para HPE 1920S)
    print("    [...] Tentando método Q-BRIDGE (VLAN-Aware)...")
    raw_results = strategy_qbridge(switch_ip, comunidade, tabela_portas)

    # Tentativa B: Standard (Ideal para Cisco/Outros)
    if not raw_results:
        print("    ⚠️  Q-BRIDGE vazio. Tentando método Padrão...")
        raw_results = strategy_standard(switch_ip, comunidade, tabela_portas)

    # Tentativa C: Legado (Contexto VLAN 1)
    if not raw_results and '@' not in comunidade:
        print("    ⚠️  Padrão vazio. Tentando contexto legado (public@1)...")
        raw_results = strategy_standard(switch_ip, comunidade + "@1", tabela_portas)

    # 3. Processamento Final (Enriquecimento)
    if not raw_results:
        print("⚠️  Nenhum dispositivo encontrado após todas as tentativas.")
        return []

    print(f"    -> Encontrados {len(raw_results)} MACs. Enriquecendo dados...")

    final_data = []
    for item in raw_results:
        mac = item['mac']

        # Vendor Lookup
        vendor_name = get_vendor_online(mac)

        # IP Lookup (ARP)
        ip_addr = tabela_arp.get(mac, "--")

        # Estimativa
        tipo_est = estimar_tipo_equipamento(vendor_name)

        sys.stdout.write(".")
        sys.stdout.flush()

        final_data.append({
            "port_raw": item['port_raw'],
            "port_name": item['port_name'], # Agora temos o nome real!
            "mac": mac,
            "ip": ip_addr,
            "vendor": vendor_name,
            "tipo": tipo_est
        })

    print(f" Ok!")
    return final_data

# --- MANIPULAÇÃO DE ARQUIVO E MENU ---

def salvar_arquivo(ip_switch, dados):
    PASTA_SAIDA = "RelatoriosSwitchs"
    if not os.path.exists(PASTA_SAIDA):
        try: os.makedirs(PASTA_SAIDA)
        except: return

    nome_arquivo = f"Relatorio_{ip_switch.replace('.', '_')}.txt"
    caminho_completo = os.path.join(PASTA_SAIDA, nome_arquivo)
    data_hoje = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    try:
        with open(caminho_completo, "w", encoding="utf-8") as f:
            f.write(f"LEVANTAMENTO: {ip_switch} em {data_hoje}\n")
            f.write("="*125 + "\n")
            f.write(f"{'PORTA':<15} | {'IP ADDRESS':<15} | {'TIPO':<18} | {'FABRICANTE':<25} | {'MAC'}\n")
            f.write("-" * 125 + "\n")
            for item in dados:
                # Trunca nome da porta se for muito longo
                p_name = (item['port_name'][:14]) if len(item['port_name']) > 14 else item['port_name']
                f.write(f"{p_name:<15} | {item['ip']:<15} | {item['tipo']:<18} | {item['vendor']:<25} | {item['mac']}\n")
        print(f"✅ Salvo em: {os.path.abspath(caminho_completo)}")
    except Exception as e:
        print(f"❌ Erro ao salvar: {e}")

def processar_alvo(ip, comunidade):
    data = get_mac_table_unified(ip, comunidade)
    if data:
        # Ordena pelo index da porta para ficar bonito no relatório
        data_sorted = sorted(data, key=lambda x: x['port_raw'])
        print(f"\n--- FIM DO SCAN DE {ip} ---")
        salvar_arquivo(ip, data_sorted)
    else:
        print(f"⚠️  Sem dados processáveis para {ip}.")

def main():
    print("=== SCANNER DE REDE UNIVERSAL (HPE 1920S + LEGACY) ===")

    while True:
        print("\n" + "="*40)
        print("1. Digitar IP manualmente")
        print("2. Carregar lista (pasta: IPsSwitchs)")
        print("0. Sair")

        opcao = input("Opção: ").strip()

        if opcao == '0': break

        elif opcao == '1':
            while True:
                ip = input("\nIP do Switch (ou 'voltar'): ").strip()
                if ip.lower() == 'voltar': break
                if not ip: continue
                comunidade = input("Comunidade [public]: ").strip() or 'public'
                processar_alvo(ip, comunidade)

        elif opcao == '2':
            PASTA_ENTRADA = "IPsSwitchs"
            if not os.path.exists(PASTA_ENTRADA):
                print(f"\n❌ Pasta '{PASTA_ENTRADA}' não encontrada!")
                print("Crie a pasta e adicione arquivos .txt com os IPs.")
                continue

            print(f"\nArquivos disponíveis:")
            try:
                arquivos = [f for f in os.listdir(PASTA_ENTRADA) if f.endswith('.txt')]
                if not arquivos:
                    print("  (Nenhum arquivo .txt encontrado)")
                    continue
                for arq in arquivos: print(f"  - {arq}")
            except: pass

            nome_arquivo = input(f"\nDigite o nome do arquivo: ").strip()
            caminho_entrada = os.path.join(PASTA_ENTRADA, nome_arquivo)

            if not os.path.isfile(caminho_entrada):
                print(f"❌ Arquivo não encontrado.")
                continue

            comunidade_padrao = input("Comunidade padrão [public]: ").strip() or 'public'

            try:
                with open(caminho_entrada, 'r', encoding='utf-8') as f:
                    ips = [linha.strip() for linha in f if linha.strip()]
            except:
                with open(caminho_entrada, 'r') as f:
                    ips = [linha.strip() for linha in f if linha.strip()]

            print(f"Carregados {len(ips)} IPs.")
            for i, ip in enumerate(ips, 1):
                print(f"\n>>> [{i}/{len(ips)}] Processando: {ip} <<<")
                processar_alvo(ip, comunidade_padrao)
            print("\n✅ Processo de lista finalizado!")

if __name__ == "__main__":
    main()
