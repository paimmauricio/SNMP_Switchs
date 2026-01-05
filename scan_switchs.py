###################################################################################################################
#Nome do Script		:  scan_switchs.py
#Descrição		    :  Fazer coorelação de porta de switchs e tipos de equipamentos
#Autor       		:  Maurício Paim
#Email         		:  paim.mauricio@gmail.com
#Data         		:  05/01/2026
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
        print("Erro: Instale 'pysnmp==4.4.12' e 'pyasn1==0.4.8'")
        sys.exit(1)

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
            # Pausa de 1.5s para evitar bloqueio da API
            time.sleep(1.5)
            return vendor
    except: pass
    return "Desconhecido"

# --- FUNÇÕES SNMP (UNIVERSAIS) ---

def get_port_names(switch_ip, comunidade):
    bridge_to_ifindex = {}
    try:
        iterator = nextCmd(SnmpEngine(), CommunityData(comunidade, mpModel=1),
                           UdpTransportTarget((switch_ip, 161), timeout=6, retries=3),
                           ContextData(), ObjectType(ObjectIdentity('1.3.6.1.2.1.17.1.4.1.2')),
                           lexicographicMode=False)
        for errorIndication, errorStatus, errorIndex, varBinds in iterator:
            if not errorIndication:
                for varBind in varBinds:
                    bridge_to_ifindex[int(varBind[0][-1])] = int(varBind[1])
    except: pass

    ifindex_to_name = {}
    try:
        iterator = nextCmd(SnmpEngine(), CommunityData(comunidade, mpModel=1),
                           UdpTransportTarget((switch_ip, 161), timeout=6, retries=3),
                           ContextData(), ObjectType(ObjectIdentity('1.3.6.1.2.1.31.1.1.1.1')),
                           lexicographicMode=False)
        for errorIndication, errorStatus, errorIndex, varBinds in iterator:
            if not errorIndication:
                for varBind in varBinds:
                    ifindex_to_name[int(varBind[0][-1])] = str(varBind[1])
    except: pass

    final_map = {}
    for b_port, if_idx in bridge_to_ifindex.items():
        final_map[b_port] = ifindex_to_name.get(if_idx, str(b_port))
    return final_map

def get_arp_table(switch_ip, comunidade):
    arp_map = {}
    try:
        iterator = nextCmd(SnmpEngine(), CommunityData(comunidade, mpModel=1),
                           UdpTransportTarget((switch_ip, 161), timeout=6, retries=3),
                           ContextData(), ObjectType(ObjectIdentity('1.3.6.1.2.1.4.22.1.2')),
                           lexicographicMode=False)
        for errorIndication, errorStatus, errorIndex, varBinds in iterator:
            if not errorIndication:
                for varBind in varBinds:
                    try:
                        mac_parts = [f"{x:02X}" for x in list(varBind[1])]
                        mac_addr = ":".join(mac_parts)
                        ip_parts = list(varBind[0])[-4:]
                        ip_addr = ".".join([str(x) for x in ip_parts])
                        arp_map[mac_addr] = ip_addr
                    except: continue
    except: pass
    return arp_map

def get_mac_table(switch_ip, comunidade):
    print(f"\n[...] Conectando ao switch {switch_ip}...")
    
    tabela_arp = get_arp_table(switch_ip, comunidade)
    tabela_nomes_portas = get_port_names(switch_ip, comunidade)
    
    results = []
    print("[...] Mapeando dispositivos...")
    
    try:
        iterator = nextCmd(SnmpEngine(), CommunityData(comunidade, mpModel=1),
                           UdpTransportTarget((switch_ip, 161), timeout=6.0, retries=3),
                           ContextData(), ObjectType(ObjectIdentity('1.3.6.1.2.1.17.4.3.1.2')),
                           lexicographicMode=False)
    except NameError:
        print("Erro de versão de biblioteca.")
        return []

    count = 0
    for errorIndication, errorStatus, errorIndex, varBinds in iterator:
        if errorIndication or errorStatus:
            print(f"❌ Falha SNMP no IP {switch_ip}")
            return []
        
        for varBind in varBinds:
            val = varBind[1]
            port_number_raw = int(val)
            nome_porta_real = tabela_nomes_portas.get(port_number_raw, str(port_number_raw))
            
            mac_decimals = list(varBind[0])[-6:] 
            mac_parts = [f"{x:02X}" for x in mac_decimals]
            mac_address = ":".join(mac_parts)
            
            vendor_name = get_vendor_online(mac_address)
            tipo_estimado = estimar_tipo_equipamento(vendor_name)
            ip_address = tabela_arp.get(mac_address, "--")
            
            sys.stdout.write(".") 
            sys.stdout.flush()
            
            results.append({
                "port_raw": port_number_raw,
                "port_name": nome_porta_real,
                "mac": mac_address,
                "ip": ip_address,
                "vendor": vendor_name,
                "tipo": tipo_estimado
            })
            count += 1
    
    print(f" Ok! ({count} disp.)")
    return results

# --- SALVAR NA PASTA 'RelatoriosSwitchs' ---
def salvar_arquivo(ip_switch, dados):
    PASTA_SAIDA = "RelatoriosSwitchs"
    
    # Cria a pasta se ela não existir
    if not os.path.exists(PASTA_SAIDA):
        try:
            os.makedirs(PASTA_SAIDA)
            print(f"📂 Pasta '{PASTA_SAIDA}' criada com sucesso.")
        except OSError as e:
            print(f"❌ Erro ao criar pasta {PASTA_SAIDA}: {e}")
            return

    nome_arquivo = f"Relatorio_{ip_switch.replace('.', '_')}.txt"
    # Caminho completo: RelatoriosSwitchs/Relatorio_X_X_X_X.txt
    caminho_completo = os.path.join(PASTA_SAIDA, nome_arquivo)
    
    data_hoje = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    
    try:
        with open(caminho_completo, "w", encoding="utf-8") as f:
            f.write(f"LEVANTAMENTO: {ip_switch} em {data_hoje}\n")
            f.write("="*120 + "\n")
            f.write(f"{'PORTA':<12} | {'IP ADDRESS':<15} | {'TIPO':<18} | {'FABRICANTE':<25} | {'MAC'}\n")
            f.write("-" * 120 + "\n")
            for item in dados:
                f.write(f"{item['port_name']:<12} | {item['ip']:<15} | {item['tipo']:<18} | {item['vendor']:<25} | {item['mac']}\n")
        
        # Mostra o caminho absoluto para confirmar onde salvou
        print(f"✅ Salvo em: {os.path.abspath(caminho_completo)}")
    except Exception as e:
        print(f"❌ Erro ao salvar arquivo: {e}")

def processar_alvo(ip, comunidade):
    data = get_mac_table(ip, comunidade)
    
    if data:
        data_sorted = sorted(data, key=lambda x: x['port_raw'])
        print(f"--- FIM DO SCAN DE {ip} ---")
        salvar_arquivo(ip, data_sorted)
    else:
        print(f"⚠️  Sem dados para {ip}.")

# --- MENU PRINCIPAL ---
def main():
    print("=== SCANNER DE REDE (COM PASTAS) ===")
    
    while True:
        print("\n" + "="*40)
        print("1. Digitar IP manualmente")
        print("2. Carregar lista (pasta: IPsSwitchs)")
        print("0. Sair")
        
        opcao = input("Opção: ").strip()
        
        if opcao == '0':
            break
            
        elif opcao == '1':
            while True:
                ip = input("\nIP do Switch (ou 'voltar'): ").strip()
                if ip.lower() == 'voltar': break
                if not ip: continue
                comunidade = input("Comunidade [public]: ").strip() or 'public'
                processar_alvo(ip, comunidade)
        
        elif opcao == '2':
            # --- CONFIGURAÇÃO DA PASTA ---
            PASTA_ENTRADA = "IPsSwitchs"
            
            # Verifica se a pasta existe antes de perguntar o arquivo
            if not os.path.exists(PASTA_ENTRADA):
                print(f"\n❌ A pasta '{PASTA_ENTRADA}' não existe!")
                print(f"Crie a pasta '{PASTA_ENTRADA}' e coloque seu arquivo .txt lá dentro.")
                continue

            print(f"\nArquivos disponíveis em '{PASTA_ENTRADA}':")
            try:
                # Lista os arquivos para ajudar o usuário
                arquivos = [f for f in os.listdir(PASTA_ENTRADA) if f.endswith('.txt')]
                if not arquivos:
                    print("  (Nenhum arquivo .txt encontrado)")
                for arq in arquivos:
                    print(f"  - {arq}")
            except: pass

            nome_arquivo = input(f"\nDigite o nome do arquivo (ex: switches.txt): ").strip()
            
            # Monta o caminho: IPsSwitchs/switches.txt
            caminho_entrada = os.path.join(PASTA_ENTRADA, nome_arquivo)
            
            if not os.path.isfile(caminho_entrada):
                print(f"❌ Arquivo não encontrado: {caminho_entrada}")
                continue
                
            comunidade_padrao = input("Comunidade padrão [public]: ").strip() or 'public'
            
            print(f"\nLendo lista de: {caminho_entrada}")
            
            # Correção do erro de indentação aqui:
            with open(caminho_entrada, 'r', encoding='utf-8') as f:
                ips = [linha.strip() for linha in f if linha.strip()]
            
            total = len(ips)
            print(f"Carregados {total} IPs.")
            
            for i, ip in enumerate(ips, 1):
                print(f"\n>>> [{i}/{total}] Processando: {ip} <<<")
                processar_alvo(ip, comunidade_padrao)
                
            print("\n✅ Processamento em lote finalizado!")

if __name__ == "__main__":
    main()
