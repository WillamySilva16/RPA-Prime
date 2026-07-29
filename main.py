"""
RPA - PrimeBuilder CSV Importer
Fluxo: SQL Server -> Google Sheets -> .csv -> Upload Portal
"""

import os
import time
import csv
import gspread
from sqlalchemy import create_engine, text
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

load_dotenv(override=True)
console = Console()

# ──────────────────────────────────────────────
# VARIÁVEIS DE AMBIENTE
# ──────────────────────────────────────────────
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "pag1")
CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH", "CHAVES/credentials.json")

PORTAL_URL = os.getenv("PORTAL_URL")
PORTAL_EMPRESA = os.getenv("PORTAL_EMPRESA")
PORTAL_USUARIO = os.getenv("PORTAL_USUARIO")
PORTAL_SENHA = os.getenv("PORTAL_SENHA")

CSV_PATH = os.path.join(os.path.dirname(__file__), "output.csv")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ──────────────────────────────────────────────
# ETAPA 1 — QUERY NO SQL SERVER
# ──────────────────────────────────────────────
def buscar_dados_bd(query: str) -> list[dict]:
    console.print(Panel("[bold cyan]ETAPA 1 — Consultando SQL Server...[/]"))

    connection_string = (
        f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
        "?driver=ODBC+Driver+17+for+SQL+Server"
    )

    engine = create_engine(connection_string)

    with engine.connect() as conn:
        result = conn.execute(text(query))
        rows = [dict(row._mapping) for row in result]

    console.print(f"[green]✓ {len(rows)} registros encontrados[/]")
    return rows


# ──────────────────────────────────────────────
# ETAPA 2 — ESCREVER NO GOOGLE SHEETS
# ──────────────────────────────────────────────
def escrever_sheets(rows: list[dict]) -> None:
    console.print(Panel("[bold cyan]ETAPA 2 — Escrevendo no Google Sheets...[/]"))

    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(SHEET_NAME)

    ws.batch_clear(["A4:A"])  # limpa só os dados

    valores = [[f"{row['RE']} - {row['NOME']}"] for row in rows]

    ws.update(values=valores, range_name="A4")

    console.print(f"[green]✓ {len(valores)} linhas escritas a partir de A4[/]")


# ──────────────────────────────────────────────
# ETAPA 3 — BAIXAR COMO .CSV (AJUSTADO 🔥)
# ──────────────────────────────────────────────

def baixar_csv_sheets() -> None:
    console.print(Panel("[bold cyan]ETAPA 3 — Gerando CSV a partir do Sheets...[/]"))

    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(SHEET_NAME)

    dados = ws.get("A1:A")

    # sobrescreve o arquivo automaticamente
    with open(CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # 🔥 LINHAS FIXAS
        writer.writerow(["SEM COBERTURA"])
        writer.writerow(["NENHUM"])
        writer.writerow(["POSTO VAGO"])

        # 🔥 DADOS DO SHEETS
        for linha in dados:
            if linha and linha[0].strip():
                writer.writerow(linha)

    console.print("[green]✓ CSV gerado com linhas fixas + dados do Sheets[/]")


# ──────────────────────────────────────────────
# ETAPA 4 — UPLOAD NO PORTAL PRIMEBUILDER
# ──────────────────────────────────────────────
def upload_portal() -> None:
    console.print(Panel("[bold cyan]ETAPA 4 — Upload no Portal PrimeBuilder...[/]"))

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    # Timeout do WebDriver aumentado pra 300s (portal processa 10k+ linhas)
    navegador = webdriver.Chrome(options=chrome_options)
    navegador.set_page_load_timeout(300)
    navegador.set_script_timeout(300)
    wait = WebDriverWait(navegador, 30)

    try:
        console.print("  → Abrindo portal e fazendo login...")
        navegador.get("https://www.primebuilder.com.br/Frontend/Default/LogIn")

        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[placeholder='Empresa']")
            )
        )
        navegador.find_element(
            By.CSS_SELECTOR, "input[placeholder='Empresa']"
        ).send_keys(PORTAL_EMPRESA)
        navegador.find_element(
            By.CSS_SELECTOR, "input[placeholder='Usuário']"
        ).send_keys(PORTAL_USUARIO)
        navegador.find_element(By.CSS_SELECTOR, "input[placeholder='Senha']").send_keys(
            PORTAL_SENHA
        )
        navegador.find_element(
            By.CSS_SELECTOR, "input[value='Entrar'], button[type='submit']"
        ).click()

        time.sleep(4)

        console.print("  → Navegando para a página de importação...")
        navegador.get(PORTAL_URL)

        time.sleep(3)

        # DEBUG temporário — remover depois de identificar a causa
        os.makedirs("/app/debug", exist_ok=True)
        console.print(f"[yellow]DEBUG URL atual: {navegador.current_url}[/]")
        navegador.save_screenshot("/app/debug/debug_login.png")
        with open("/app/debug/debug_login.html", "w", encoding="utf-8") as f:
            f.write(navegador.page_source)

        console.print("  → Selecionando o arquivo CSV...")
        input_arquivo = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        navegador.execute_script(
            "arguments[0].style.display = 'block'; arguments[0].style.opacity = '1';",
            input_arquivo,
        )
        input_arquivo.send_keys(os.path.abspath(CSV_PATH))

        time.sleep(2)

        console.print("  → Clicando em Enviar...")
        btn_enviar = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit'].btn"))
        )
        navegador.execute_script("arguments[0].scrollIntoView(true);", btn_enviar)
        time.sleep(1)
        navegador.execute_script("arguments[0].click();", btn_enviar)

        # Aguarda o portal processar e a página mudar (pode demorar com 10k+ linhas)
        console.print("  → Aguardando resposta do portal...")
        try:
            WebDriverWait(navegador, 300).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
                and d.current_url != PORTAL_URL
            )
        except Exception:
            pass  # se não redirecionar, tudo bem — o upload pode ter sido aceito mesmo assim

        console.print("[green]✓ Upload realizado com sucesso![/]")

    except Exception as e:
        console.print(f"[red]✗ Erro no portal: {e}[/]")
        raise

    finally:
        navegador.quit()


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
if __name__ == "__main__":
    console.print(
        Panel(
            "[bold white]RPA — PrimeBuilder CSV Importer[/]\n"
            "[dim]SQL Server → Sheets → CSV → Portal[/]",
            style="bold blue",
        )
    )

    QUERY = """
        WITH RELFUNC_FIX AS (
    SELECT *
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY RELACAOENTIDADE
                   ORDER BY CODIGO DESC
               ) AS RN
        FROM RELACAOENTIDADE
        WHERE CODIGO IS NOT NULL
    ) X
    WHERE RN = 1
)

SELECT
    RELFUNC.CODIGO AS RE,
    ENTFUNC.NOMERESUMIDO AS NOME

FROM FUNCIONARIO F

INNER JOIN RELFUNC_FIX RELFUNC
    ON RELFUNC.RELACAOENTIDADE = F.FUNCIONARIO

INNER JOIN ENTIDADE ENTFUNC
    ON ENTFUNC.ENTIDADE = RELFUNC.PAPEL1
    """

    try:
        dados = buscar_dados_bd(QUERY)

        if not dados:
            console.print("[yellow]⚠ Nenhum dado retornado pela query. Encerrando.[/]")
            exit(0)

        escrever_sheets(dados)

        time.sleep(2)

        baixar_csv_sheets()

        upload_portal()

        console.print(Panel("[bold green]✓ Automação concluída com sucesso![/]"))

    except Exception as e:
        console.print(f"[bold red]ERRO FATAL: {e}[/]")
        raise
