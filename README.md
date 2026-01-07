![Logo of the project](https://github.com/paimmauricio/Script-Rede/blob/main/imagens/logo.png)

# 🕵️‍♂️ SNMP Switch Port Mapper & Device Identifier

Este script em Python realiza o mapeamento automático de portas de switches de rede (Aruba, Cisco, HP, Dell, etc.) utilizando o protocolo SNMP. Ele identifica dispositivos conectados, resolve nomes de fabricantes via API online e estima o tipo de equipamento (PDV, Câmera, PC, etc.) para auxiliar em inventários de rede.

## 🚀 Funcionalidades

-   **Mapeamento Universal:** Compatível com qualquer switch que suporte Bridge-MIB (RFC 1493).
-   **Tradução de Portas:** Converte IDs internos SNMP para nomes reais de interfaces (ex: `Gi1/0/1` ou `Port 1`).
-   **Identificação de Fabricante:** Consulta automática à API *MacVendors* para descobrir a marca do dispositivo.
-   **Classificação Inteligente:** Estima o tipo de dispositivo (PDV, Coletor, Câmera, PC) com base no fabricante (personalizável).
-   **Modo Híbrido:**
    -   *Manual:* Escaneia um único IP digitado.
    -   *Lote (Batch):* Lê uma lista de IPs de um arquivo `.txt` e processa todos sequencialmente.
-   **Exportação Automática:** Gera relatórios em `.txt` organizados por data e IP.

  ## 🚀 Novidades na Versão Universal

Este script foi atualizado para atuar como um Scanner Universal de Switches, resolvendo problemas de compatibilidade com a linha HPE OfficeConnect.

### Funcionalidades
* **Estratégia Híbrida Inteligente:**
    1.  Tenta leitura via **Q-BRIDGE MIB** (Ideal para HPE 1920S e switches modernos/Linux).
    2.  Se falhar, tenta leitura via **Standard Bridge MIB** (Cisco, TP-Link, etc).
    3.  Último recurso: Tenta contexto de VLAN Legado (`community@1`).
* **Mapeamento Real de Portas:** Cruza o índice SNMP com a descrição da interface (ex: exibe `GE1/0/24` em vez de `24`).
* **Identificação de Dispositivos:** Consulta API online para identificar o fabricante do dispositivo conectado (Apple, Dell, Intel, etc).

### 📦 Instalação
```bash
pip install pysnmp requests
```
### 🛠️ Pré-requisitos

-   Python 3.6+
-   Acesso de rede aos switches (porta 161 UDP liberada).
-   Comunidade SNMP configurada nos switches (Padrão no script: `public`, mas solicitada na execução).
-   Conexão com Internet (para consulta de API de fabricantes).

## 📦 Instalação

Devido a mudanças recentes na biblioteca `pysnmp`, é **necessário** instalar versões específicas para garantir a compatibilidade.

1.  **Clone o repositório:**
    ```bash
    git clone [https://github.com/paimmauricio/SNMP_Switchs.git](https://github.com/paimmauricio/SNMP_Switchs.git)
    cd SNMP_Switchs
    ```

2.  **Crie um ambiente virtual (Recomendado):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # Linux/Mac
    # ou
    venv\Scripts\activate     # Windows
    ```

3.  **Instale as dependências exatas:**
    ```bash
    pip install requests "pysnmp==4.4.12" "pyasn1==0.4.8"
    ```

## 📂 Estrutura de Pastas

O script gerencia automaticamente a estrutura de diretórios:

```text
.
├── scan_switchs.py       # O script principal
├── IPsSwitchs/           # (Entrada) Coloque seus arquivos .txt com listas de IPs aqui
│   └── lojas_zona_sul.txt
└── RelatoriosSwitchs/    # (Saída) Onde os relatórios gerados serão salvos
    └── Relatorio_192_168_0_10.txt
```
# 🚀 Como Usar

Execute o script no terminal:

```bash
python scan_switchs.py
```

Você verá um menu interativo:

### Opção 1: Digitar IP manualmente
Ideal para testes rápidos.

1. Digite o **IP** do switch.
2. Confirme a comunidade **SNMP**.
3. O resultado aparece na tela e é salvo na pasta `RelatoriosSwitchs/`.

### Opção 2: Carregar lista (Lote)
Ideal para inventário de grandes redes.

1. Crie um arquivo `.txt` dentro da pasta `IPsSwitchs/`.
2. Coloque um IP por linha (Exemplo):

```text
192.168.1.10
192.168.1.11
10.0.0.254
```

3. No menu do script, escolha a opção 2 e digite o nome do arquivo (ex: `switches.txt`).

## ⚙️ Personalização

### Adicionar novos tipos de dispositivos
No arquivo `scan_switchs.py`, você pode editar a função `estimar_tipo_equipamento` para adicionar regras específicas do seu negócio:

```python
if "nome_do_fabricante" in v: return "Novo Tipo"
```

## 📝 Exemplo de Saída (Relatório)

```text
LEVANTAMENTO: 192.168.1.10 em 05/01/2026 14:00
========================================================================================================================
PORTA        | IP ADDRESS      | TIPO               | FABRICANTE                | MAC
------------------------------------------------------------------------------------------------------------------------
1            | 192.168.1.50    | PDV                | Toshiba Global Commerce.. | 24:2F:FA:XX:XX:XX
2            | --              | Coletor/Impressora | Zebra Technologies Inc    | 10:4F:58:XX:XX:XX
48           | 10.0.0.1        | Rede/Wifi          | Cisco Systems             | 00:11:22:XX:XX:XX
```

## 🤝 Contribuição
Sinta-se à vontade para abrir Issues ou Pull Requests para melhorar a detecção de dispositivos ou compatibilidade com novos switches.

## 📄 Licença
Este projeto está sob a licença MIT.

---
## ⚠️ Importante
- **Execute antes em uma máquina virtual**
- **Crie um ponto de restauração**
- **Se algo não funcionar como esperado, use a opção de restauração** para voltar ao estado anterior.
- **Este script foi testado em versões recentes do Linux Parrot e Oracle**, mas recomenda-se criar um backup completo do sistema antes de utilizá-lo.

---

## ❤️ Todo apoio é bem vindo ❤️
|💳 Transferência Unibanco |🏦 Pix |💰 QR Code PayPal|🌍 Site PayPal|
|----------------------------------- | -------------- |-------------------------|----------------------|
| **Agência:** 8488 <br> **C/C:** 0047854-9| paim.mauricio@gmail.com|[![QR Code PayPal](https://github.com/paimmauricio/paimmauricio/blob/main/QR_Code_PayPal.png)](https://github.com/paimmauricio/paimmauricio/blob/main/QR_Code_PayPal.png)|[Doação Direta pelo PayPal](https://www.paypal.com/donate?hosted_button_id=YJNX67EAAHNCU)|
