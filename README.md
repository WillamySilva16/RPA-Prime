# RPA — PrimeBuilder CSV Importer

Automação completa: **SQL Server → Google Sheets → .csv → Upload Portal PrimeBuilder**

---

## Estrutura

```
rpa_primebuilder/
├── main.py              # Script principal
├── .env                 # Variáveis de ambiente
├── requirements.txt     # Dependências
├── output.csv           # Gerado automaticamente na etapa 3
└── CHAVES/
    └── credentials.json # Service account do GCP
```

---

## Setup

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Configurar o `.env`
Preencha com seus dados reais (IP do SQL Server, credenciais, etc.)

### 3. Credenciais Google (Service Account)
- Acesse o GCP → IAM → Service Accounts
- Crie ou use uma existente → gere uma chave JSON
- Salve em `CHAVES/credentials.json`
- **Compartilhe o Sheets com o e-mail da service account** (permissão de Editor)

### 4. Plugar a query
No final do `main.py`, substitua o valor de `QUERY` pela sua query real:
```python
QUERY = """
    SELECT RE, NOME
    FROM sua_tabela
    WHERE sua_condicao = 1
"""
```

---

## Rodar

```bash
python main.py
```

---

## O que o script faz

| Etapa | O que faz |
|-------|-----------|
| 1 | Conecta no SQL Server via SQLAlchemy e executa a query |
| 2 | Une as colunas `RE` e `NOME` no formato `RE - NOME` e escreve no Sheets a partir da linha 4 (A4) |
| 3 | Salva o mesmo conteúdo como `output.csv` (1 coluna, sem header) |
| 4 | Abre o Chrome, faz login no PrimeBuilder, navega para a página de importação, seleciona o CSV e clica em Enviar |

---

## Observações

- O `output.csv` é **sobrescrito a cada execução**
- O Sheets **não limpa** as linhas anteriores antes de escrever — se quiser limpar primeiro, descomente a linha `ws.clear()` no código (cuidado pra não apagar as linhas 1-3 fixas!)
- O Chrome abre visualmente por padrão; para rodar sem janela, descomente `--headless=new` no `main.py`
- Os nomes das colunas do BD precisam ser exatamente `RE` e `NOME` (case-insensitive no SQL Server, mas verifique o alias na sua query)
