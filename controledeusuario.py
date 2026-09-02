import customtkinter as ctk
import json, os, re, shutil, hashlib, threading
from datetime import datetime
from collections import defaultdict
import tkinter.messagebox as messagebox

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

# ── Tema ───────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ARQUIVO_DADOS    = "clientes.json"
ARQUIVO_USUARIOS = "usuarios.json"
ARQUIVO_LOG      = "log_acoes.json"
PASTA_BACKUP     = "backups"
MAX_HISTORICO_BUSCA = 10

# ── Permissões por perfil ──────────────────────────────────────────────────────
# admin → tudo; user → não pode excluir nem alternar status
PERMISSOES = {
    "admin": {"excluir", "alternar_status", "editar", "cadastrar", "ver_log"},
    "user":  {"editar", "cadastrar"},
}

COR_PRIMARIA  = "#3B82F6"
COR_PERIGO    = "#EF4444"
COR_SUCESSO   = "#22C55E"
COR_AMARELO   = "#F59E0B"
COR_INATIVO   = "#64748B"
COR_CARD      = "#1E293B"
COR_FUNDO     = "#0F172A"
COR_TEXTO_SUB = "#94A3B8"
COR_BORDA     = "#334155"
COR_TOPO      = "#0B1120"

MESES_PT = ["Jan","Fev","Mar","Abr","Mai","Jun",
            "Jul","Ago","Set","Out","Nov","Dez"]

# ══════════════════════════════════════════════════════════════════════════════
#  UTILITÁRIOS
# ══════════════════════════════════════════════════════════════════════════════
def hash_senha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

# ── Usuários ──────────────────────────────────────────────────────────────────
def carregar_usuarios() -> dict:
    if os.path.exists(ARQUIVO_USUARIOS):
        with open(ARQUIVO_USUARIOS, "r", encoding="utf-8") as f:
            return json.load(f)
    # Usuário padrão: admin / 1234
    dados = {"usuarios": [{"usuario": "admin", "senha_hash": hash_senha("1234"),
                            "perfil": "admin", "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M")}]}
    salvar_usuarios(dados)
    return dados

def salvar_usuarios(dados: dict):
    with open(ARQUIVO_USUARIOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

def autenticar(usuario: str, senha: str) -> dict | None:
    dados = carregar_usuarios()
    for u in dados.get("usuarios", []):
        if u["usuario"].lower() == usuario.lower() and u["senha_hash"] == hash_senha(senha):
            return u
    return None

# ── Log de ações ──────────────────────────────────────────────────────────────
def carregar_log() -> list:
    if os.path.exists(ARQUIVO_LOG):
        with open(ARQUIVO_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def registrar_log(usuario: str, acao: str, detalhe: str = ""):
    log = carregar_log()
    log.append({
        "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "usuario":   usuario,
        "acao":      acao,
        "detalhe":   detalhe,
    })
    # Mantém apenas os últimos 500 registros
    if len(log) > 500:
        log = log[-500:]
    with open(ARQUIVO_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def tem_permissao(perfil: str, acao: str) -> bool:
    return acao in PERMISSOES.get(perfil, set())

# ── Clientes ──────────────────────────────────────────────────────────────────
def carregar_clientes() -> list:
    if os.path.exists(ARQUIVO_DADOS):
        with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def salvar_clientes(clientes: list):
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
        json.dump(clientes, f, ensure_ascii=False, indent=4)

def fazer_backup():
    if not os.path.exists(ARQUIVO_DADOS):
        return
    os.makedirs(PASTA_BACKUP, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(PASTA_BACKUP, f"clientes_{ts}.json")
    shutil.copy2(ARQUIVO_DADOS, dest)
    arquivos = sorted([f for f in os.listdir(PASTA_BACKUP) if f.endswith(".json")])
    for antigo in arquivos[:-10]:
        os.remove(os.path.join(PASTA_BACKUP, antigo))

# ── Formatadores ──────────────────────────────────────────────────────────────
def formatar_cpf(cpf: str) -> str:
    d = re.sub(r"\D","",cpf)[:11]
    if len(d)<=3:  return d
    if len(d)<=6:  return f"{d[:3]}.{d[3:]}"
    if len(d)<=9:  return f"{d[:3]}.{d[3:6]}.{d[6:]}"
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"

def formatar_telefone(tel: str) -> str:
    d = re.sub(r"\D","",tel)[:11]
    if len(d)<=2:  return f"({d}"
    if len(d)<=6:  return f"({d[:2]}) {d[2:]}"
    if len(d)<=10: return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return f"({d[:2]}) {d[2:7]}-{d[7:]}"

def formatar_cep(cep: str) -> str:
    d = re.sub(r"\D","",cep)[:8]
    if len(d)>5: return f"{d[:5]}-{d[5:]}"
    return d

def buscar_cep(cep: str) -> dict | None:
    if not REQUESTS_OK:
        return None
    cep_limpo = re.sub(r"\D","",cep)
    if len(cep_limpo) != 8:
        return None
    try:
        r = requests.get(f"https://viacep.com.br/ws/{cep_limpo}/json/", timeout=5)
        data = r.json()
        if "erro" in data:
            return None
        return data
    except Exception:
        return None

class Separador(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, height=1, fg_color=COR_BORDA, **kw)


# ══════════════════════════════════════════════════════════════════════════════
#  TELA DE LOGIN
# ══════════════════════════════════════════════════════════════════════════════
class TelaLogin(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Login — Cadastro de Clientes")
        self.geometry("420x520")
        self.resizable(False, False)
        self.configure(fg_color=COR_FUNDO)
        self.usuario_logado = None
        self._construir()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _construir(self):
        card = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=20)
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.82, relheight=0.86)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🔐", font=ctk.CTkFont(size=54)
                     ).grid(row=0, column=0, pady=(32,4))
        ctk.CTkLabel(card, text="Cadastro de Clientes",
                     font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold")
                     ).grid(row=1, column=0, pady=(0,4))
        ctk.CTkLabel(card, text="Faça login para continuar",
                     font=ctk.CTkFont(family="Segoe UI", size=12),
                     text_color=COR_TEXTO_SUB
                     ).grid(row=2, column=0, pady=(0,20))

        def entry(row, placeholder, show=None):
            e = ctk.CTkEntry(card, placeholder_text=placeholder,
                             show=show, height=42, width=260, corner_radius=10,
                             font=ctk.CTkFont(family="Segoe UI", size=14),
                             border_width=1, border_color=COR_BORDA)
            e.grid(row=row, column=0, pady=(0,10))
            return e

        self.entry_usuario = entry(3, "Usuário")
        self.entry_senha   = entry(4, "Senha", show="●")
        self.entry_usuario.focus()

        self.lbl_erro = ctk.CTkLabel(card, text="",
                                     font=ctk.CTkFont(size=12), text_color=COR_PERIGO)
        self.lbl_erro.grid(row=5, column=0, pady=(0,8))

        ctk.CTkButton(card, text="Entrar", height=42, width=260, corner_radius=10,
                      font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                      fg_color=COR_PRIMARIA, hover_color="#2563EB",
                      command=self._verificar
                      ).grid(row=6, column=0, pady=(0,16))

        ctk.CTkLabel(card, text="Usuário padrão: admin  |  Senha: 1234",
                     font=ctk.CTkFont(size=10), text_color="#3B4A60"
                     ).grid(row=7, column=0, pady=(0,32))

        for w in (self.entry_usuario, self.entry_senha):
            w.bind("<Return>", lambda e: self._verificar())

    def _verificar(self):
        usuario = self.entry_usuario.get().strip()
        senha   = self.entry_senha.get()
        if not usuario or not senha:
            self.lbl_erro.configure(text="❌  Preencha usuário e senha.")
            return
        u = autenticar(usuario, senha)
        if u:
            self.usuario_logado = u
            registrar_log(u["usuario"], "LOGIN", "Acesso ao sistema")
            self.destroy()
        else:
            self.lbl_erro.configure(text="❌  Usuário ou senha incorretos.")
            self.entry_senha.delete(0,"end")
            self.entry_senha.focus()


# ══════════════════════════════════════════════════════════════════════════════
#  APP PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
class App(ctk.CTk):
    def __init__(self, usuario_logado: dict):
        super().__init__()
        self.title("Cadastro de Clientes")
        self.geometry("1240x780")
        self.minsize(1000, 660)
        self.configure(fg_color=COR_FUNDO)

        global FONTE_TITULO, FONTE_SECAO, FONTE_CAMPO, FONTE_LABEL
        global FONTE_CARD_N, FONTE_CARD_D, FONTE_STAT
        FONTE_TITULO = ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        FONTE_SECAO  = ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        FONTE_CAMPO  = ctk.CTkFont(family="Segoe UI", size=13)
        FONTE_LABEL  = ctk.CTkFont(family="Segoe UI", size=11)
        FONTE_CARD_N = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        FONTE_CARD_D = ctk.CTkFont(family="Segoe UI", size=12)
        FONTE_STAT   = ctk.CTkFont(family="Segoe UI", size=28, weight="bold")

        fazer_backup()

        self.usuario_logado  = usuario_logado
        self.clientes        = carregar_clientes()
        self.idx_editando    = None
        self._notif_job      = None
        self.ordenacao       = "recente"
        self.filtro_letra    = "Todos"
        self.filtro_status   = "Todos"   # "Todos" | "ativo" | "inativo"
        self.aba_atual       = "dashboard"
        self.historico_busca = []        # lista das últimas buscas

        self._construir_ui()
        self._mostrar_aba("dashboard")

    # ══════════════════════════════════════════════════════════════════════════
    #  LAYOUT RAIZ
    # ══════════════════════════════════════════════════════════════════════════
    def _construir_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._barra_topo()

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=1, column=0, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self._construir_dashboard()
        self._construir_aba_clientes()

    # ── Barra topo ────────────────────────────────────────────────────────────
    def _barra_topo(self):
        barra = ctk.CTkFrame(self, fg_color=COR_TOPO, corner_radius=0, height=56)
        barra.grid(row=0, column=0, sticky="ew")
        barra.grid_propagate(False)
        barra.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(barra, text="  👥  Clientes",
                     font=FONTE_TITULO, text_color="white"
                     ).grid(row=0, column=0, padx=20, pady=10, sticky="w")

        self.btn_nav_dash = ctk.CTkButton(
            barra, text="📊  Dashboard", width=140, height=34,
            corner_radius=8, font=FONTE_SECAO,
            fg_color=COR_PRIMARIA, hover_color="#2563EB",
            command=lambda: self._mostrar_aba("dashboard"))
        self.btn_nav_dash.grid(row=0, column=1, padx=(20,6), pady=10)

        self.btn_nav_cli = ctk.CTkButton(
            barra, text="👥  Clientes", width=140, height=34,
            corner_radius=8, font=FONTE_SECAO,
            fg_color="#1E293B", hover_color="#263448",
            command=lambda: self._mostrar_aba("clientes"))
        self.btn_nav_cli.grid(row=0, column=2, padx=(0,6), pady=10)

        self.lbl_contador_topo = ctk.CTkLabel(
            barra, text="", font=FONTE_LABEL, text_color=COR_TEXTO_SUB)
        self.lbl_contador_topo.grid(row=0, column=3, padx=10, sticky="e")

        # Usuário logado
        perfil_txt = f"👤  {self.usuario_logado['usuario']}"
        if self.usuario_logado.get("perfil") == "admin":
            perfil_txt += "  (admin)"
        ctk.CTkLabel(barra, text=perfil_txt,
                     font=FONTE_LABEL, text_color=COR_TEXTO_SUB
                     ).grid(row=0, column=4, padx=(0,6), pady=10)

        # Gerenciar usuários (apenas admin)
        if self.usuario_logado.get("perfil") == "admin":
            ctk.CTkButton(
                barra, text="👥", width=36, height=34,
                corner_radius=8, font=FONTE_SECAO,
                fg_color="#1E293B", hover_color="#263448",
                command=self._gerenciar_usuarios
            ).grid(row=0, column=5, padx=(0,4), pady=10)

            ctk.CTkButton(
                barra, text="📋 Log", width=70, height=34,
                corner_radius=8, font=FONTE_LABEL,
                fg_color="#1E293B", hover_color="#263448",
                command=self._ver_log
            ).grid(row=0, column=6, padx=(0,4), pady=10)

        self.lbl_notif = ctk.CTkLabel(
            barra, text="", font=FONTE_CAMPO,
            text_color=COR_SUCESSO, fg_color="transparent")
        self.lbl_notif.grid(row=0, column=6, padx=20, sticky="e")

    def _mostrar_aba(self, aba):
        self.aba_atual = aba
        if aba == "dashboard":
            self.frame_dashboard.grid()
            self.frame_clientes.grid_remove()
            self.btn_nav_dash.configure(fg_color=COR_PRIMARIA)
            self.btn_nav_cli.configure(fg_color="#1E293B")
            self._atualizar_dashboard()
        else:
            self.frame_clientes.grid()
            self.frame_dashboard.grid_remove()
            self.btn_nav_cli.configure(fg_color=COR_PRIMARIA)
            self.btn_nav_dash.configure(fg_color="#1E293B")
            self._atualizar_lista()
        self._atualizar_contador_topo()

    # ══════════════════════════════════════════════════════════════════════════
    #  DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════
    def _construir_dashboard(self):
        self.frame_dashboard = ctk.CTkFrame(self.container, fg_color="transparent")
        self.frame_dashboard.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        self.frame_dashboard.grid_columnconfigure((0,1,2,3), weight=1)
        self.frame_dashboard.grid_rowconfigure(1, weight=1)

        self.card_total   = self._stat_card(self.frame_dashboard, 0, 0, "Total",          "0", COR_PRIMARIA, "👥")
        self.card_ativos  = self._stat_card(self.frame_dashboard, 0, 1, "Ativos",          "0", COR_SUCESSO,  "✅")
        self.card_inativos= self._stat_card(self.frame_dashboard, 0, 2, "Inativos",        "0", COR_INATIVO,  "⏸️")
        self.card_hoje    = self._stat_card(self.frame_dashboard, 0, 3, "Cadastrados Hoje","0", COR_AMARELO,  "📅")

        frame_g = ctk.CTkFrame(self.frame_dashboard, fg_color=COR_CARD, corner_radius=14)
        frame_g.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=(14,0))
        frame_g.grid_columnconfigure(0, weight=1)
        frame_g.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(frame_g, text="📈  Cadastros por Mês (ano atual)",
                     font=FONTE_SECAO, anchor="w"
                     ).grid(row=0, column=0, padx=20, pady=(14,6), sticky="w")

        self.frame_grafico_interno = ctk.CTkFrame(frame_g, fg_color="transparent")
        self.frame_grafico_interno.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))
        self.frame_grafico_interno.grid_columnconfigure(0, weight=1)
        self.frame_grafico_interno.grid_rowconfigure(0, weight=1)
        self.canvas_grafico = None

    def _stat_card(self, parent, row, col, titulo, valor, cor, icone):
        pad_left = 0 if col == 0 else 10
        card = ctk.CTkFrame(parent, fg_color=COR_CARD, corner_radius=14)
        card.grid(row=row, column=col, padx=(pad_left,0), sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=icone, font=ctk.CTkFont(size=28)).grid(row=0, column=0, pady=(16,2))
        lbl = ctk.CTkLabel(card, text=valor, font=FONTE_STAT, text_color=cor)
        lbl.grid(row=1, column=0, pady=2)
        ctk.CTkLabel(card, text=titulo, font=FONTE_LABEL, text_color=COR_TEXTO_SUB).grid(row=2, column=0, pady=(0,16))
        return lbl

    def _atualizar_dashboard(self):
        hoje  = datetime.now().strftime("%d/%m/%Y")
        total = len(self.clientes)
        ativos   = sum(1 for c in self.clientes if c.get("status","ativo")=="ativo")
        inativos = total - ativos
        hoje_n   = sum(1 for c in self.clientes if c.get("cadastrado_em","").startswith(hoje))
        self.card_total.configure(text=str(total))
        self.card_ativos.configure(text=str(ativos))
        self.card_inativos.configure(text=str(inativos))
        self.card_hoje.configure(text=str(hoje_n))
        self._desenhar_grafico()

    def _desenhar_grafico(self):
        for w in self.frame_grafico_interno.winfo_children():
            w.destroy()
        if self.canvas_grafico:
            plt.close("all")
            self.canvas_grafico = None

        if not MATPLOTLIB_OK:
            ctk.CTkLabel(self.frame_grafico_interno,
                         text="⚠️  pip install matplotlib",
                         font=FONTE_CAMPO, text_color=COR_TEXTO_SUB
                         ).grid(row=0, column=0, pady=40)
            return

        ano = datetime.now().year
        contagem = defaultdict(int)
        for c in self.clientes:
            try:
                dt = datetime.strptime(c.get("cadastrado_em",""), "%d/%m/%Y %H:%M")
                if dt.year == ano:
                    contagem[dt.month] += 1
            except Exception:
                pass

        valores = [contagem.get(m,0) for m in range(1,13)]
        fig, ax = plt.subplots(figsize=(10,3.0), dpi=88)
        fig.patch.set_facecolor("#1E293B")
        ax.set_facecolor("#162032")
        cores = [COR_PRIMARIA if v==max(valores) else "#334F7A" for v in valores]
        bars  = ax.bar(MESES_PT, valores, color=cores, width=0.6, zorder=3)
        for bar, val in zip(bars, valores):
            if val > 0:
                ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.05,
                        str(val), ha="center", va="bottom",
                        color="white", fontsize=9, fontweight="bold")
        ax.set_ylim(0, max(max(valores)+2, 5))
        ax.tick_params(colors="#94A3B8", labelsize=9)
        ax.spines[:].set_visible(False)
        ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
        ax.grid(axis="y", color="#334155", linestyle="--", alpha=0.5, zorder=0)
        fig.tight_layout(pad=1.2)
        canvas = FigureCanvasTkAgg(fig, master=self.frame_grafico_interno)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.canvas_grafico = canvas

    # ══════════════════════════════════════════════════════════════════════════
    #  ABA CLIENTES
    # ══════════════════════════════════════════════════════════════════════════
    def _construir_aba_clientes(self):
        self.frame_clientes = ctk.CTkFrame(self.container, fg_color="transparent")
        self.frame_clientes.grid(row=0, column=0, sticky="nsew")
        self.frame_clientes.grid_columnconfigure(0, weight=5, minsize=390)
        self.frame_clientes.grid_columnconfigure(1, weight=7)
        self.frame_clientes.grid_rowconfigure(0, weight=1)
        self._painel_form()
        self._painel_lista()

    # ── Formulário ────────────────────────────────────────────────────────────
    def _painel_form(self):
        self.frame_form = ctk.CTkFrame(self.frame_clientes, fg_color=COR_CARD, corner_radius=14)
        self.frame_form.grid(row=0, column=0, padx=(14,7), pady=14, sticky="nsew")
        self.frame_form.grid_columnconfigure(0, weight=1)

        self.lbl_form_titulo = ctk.CTkLabel(
            self.frame_form, text="Novo Cliente", font=FONTE_TITULO, anchor="w")
        self.lbl_form_titulo.grid(row=0, column=0, padx=20, pady=(18,2), sticky="w")

        ctk.CTkLabel(self.frame_form, text="Campos com * são obrigatórios",
                     font=FONTE_LABEL, text_color=COR_TEXTO_SUB
                     ).grid(row=1, column=0, padx=20, pady=(0,8), sticky="w")

        Separador(self.frame_form).grid(row=2, column=0, padx=20, pady=(0,8), sticky="ew")

        # ── Identificação ─────────────────────────────────────────────────────
        self._secao(3, "  Identificação")
        self.entry_nome  = self._campo(4,  "Nome Completo *",  "ex: Maria Oliveira Santos")
        self.entry_cpf   = self._campo(6,  "CPF",              "ex: 000.000.000-00")
        self.entry_email = self._campo(8,  "E-mail",           "ex: maria@email.com")

        Separador(self.frame_form).grid(row=10, column=0, padx=20, pady=(6,8), sticky="ew")

        # ── Contato & Localização ─────────────────────────────────────────────
        self._secao(11, "  Contato & Localização")
        self.entry_telefone   = self._campo(12, "Telefone *",          "ex: (71) 99999-0000")

        # CEP com botão buscar
        ctk.CTkLabel(self.frame_form, text="CEP", font=FONTE_LABEL,
                     text_color=COR_TEXTO_SUB, anchor="w"
                     ).grid(row=14, column=0, padx=22, pady=(6,1), sticky="w")

        cep_row = ctk.CTkFrame(self.frame_form, fg_color="transparent")
        cep_row.grid(row=15, column=0, padx=20, pady=(0,2), sticky="ew")
        cep_row.grid_columnconfigure(0, weight=1)

        self.entry_cep = ctk.CTkEntry(cep_row, placeholder_text="ex: 40000-000",
                                      height=36, corner_radius=8, font=FONTE_CAMPO,
                                      border_width=1, border_color=COR_BORDA)
        self.entry_cep.grid(row=0, column=0, sticky="ew", padx=(0,6))

        self.btn_cep = ctk.CTkButton(cep_row, text="🔍 Buscar", width=90, height=36,
                                     corner_radius=8, font=FONTE_LABEL,
                                     fg_color="#1E3A5F", hover_color="#163050",
                                     command=self._buscar_cep)
        self.btn_cep.grid(row=0, column=1)

        self.lbl_cep_status = ctk.CTkLabel(self.frame_form, text="",
                                           font=FONTE_LABEL, text_color=COR_SUCESSO)
        self.lbl_cep_status.grid(row=16, column=0, padx=22, pady=(0,2), sticky="w")

        self.entry_endereco   = self._campo(17, "Endereço *",          "ex: Rua das Flores, 123")
        self.entry_referencia = self._campo(19, "Ponto de Referência", "ex: Próximo ao Mercadão")

        Separador(self.frame_form).grid(row=21, column=0, padx=20, pady=(6,8), sticky="ew")

        # ── Status ────────────────────────────────────────────────────────────
        self._secao(22, "  Status do Cliente")
        status_row = ctk.CTkFrame(self.frame_form, fg_color="transparent")
        status_row.grid(row=23, column=0, padx=20, pady=(4,4), sticky="ew")
        self.var_status = ctk.StringVar(value="ativo")

        ctk.CTkRadioButton(status_row, text="✅ Ativo", variable=self.var_status,
                           value="ativo", font=FONTE_CAMPO,
                           fg_color=COR_SUCESSO, hover_color="#16A34A"
                           ).pack(side="left", padx=(0,20))
        ctk.CTkRadioButton(status_row, text="⏸️ Inativo", variable=self.var_status,
                           value="inativo", font=FONTE_CAMPO,
                           fg_color=COR_INATIVO, hover_color="#475569"
                           ).pack(side="left")

        Separador(self.frame_form).grid(row=24, column=0, padx=20, pady=(6,8), sticky="ew")

        # ── Observações ───────────────────────────────────────────────────────
        self._secao(25, "  Observações")
        self.text_obs = ctk.CTkTextbox(
            self.frame_form, height=70, corner_radius=8,
            font=FONTE_CAMPO, border_width=1, border_color=COR_BORDA)
        self.text_obs.grid(row=26, column=0, padx=20, pady=(4,4), sticky="ew")

        # ── Botões ────────────────────────────────────────────────────────────
        self.btn_salvar = ctk.CTkButton(
            self.frame_form, text="💾   Salvar Cliente", height=44, corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=COR_PRIMARIA, hover_color="#2563EB",
            command=self._salvar_cliente)
        self.btn_salvar.grid(row=27, column=0, padx=20, pady=(14,6), sticky="ew")

        self.btn_cancelar = ctk.CTkButton(
            self.frame_form, text="✖   Cancelar Edição", height=36, corner_radius=10,
            font=FONTE_CAMPO, fg_color="#1E3A5F", hover_color="#1E2D45",
            text_color="#93C5FD", command=self._cancelar_edicao)
        self.btn_cancelar.grid(row=28, column=0, padx=20, pady=(0,20), sticky="ew")
        self.btn_cancelar.grid_remove()

        # Binds
        self.entry_cpf.bind("<KeyRelease>",      self._mask_cpf)
        self.entry_telefone.bind("<KeyRelease>",  self._mask_tel)
        self.entry_cep.bind("<KeyRelease>",       self._mask_cep_key)
        self.entry_cep.bind("<FocusOut>",         lambda e: self._buscar_cep_auto())

        for entry in (self.entry_nome, self.entry_cpf, self.entry_email,
                      self.entry_telefone, self.entry_cep,
                      self.entry_endereco, self.entry_referencia):
            entry.bind("<Return>", lambda e: self._salvar_cliente())
            entry.bind("<Escape>", lambda e: self._cancelar_edicao())

        self.protocol("WM_DELETE_WINDOW", self._confirmar_fechar)

    def _secao(self, row, texto):
        ctk.CTkLabel(self.frame_form, text=texto, font=FONTE_SECAO,
                     text_color=COR_PRIMARIA, anchor="w"
                     ).grid(row=row, column=0, padx=20, pady=(4,2), sticky="w")

    def _campo(self, row, label, placeholder):
        ctk.CTkLabel(self.frame_form, text=label, font=FONTE_LABEL,
                     text_color=COR_TEXTO_SUB, anchor="w"
                     ).grid(row=row, column=0, padx=22, pady=(6,1), sticky="w")
        e = ctk.CTkEntry(self.frame_form, placeholder_text=placeholder,
                         height=36, corner_radius=8, font=FONTE_CAMPO,
                         border_width=1, border_color=COR_BORDA)
        e.grid(row=row+1, column=0, padx=20, pady=(0,2), sticky="ew")
        return e

    # ── Painel lista ───────────────────────────────────────────────────────────
    def _painel_lista(self):
        frame = ctk.CTkFrame(self.frame_clientes, fg_color=COR_CARD, corner_radius=14)
        frame.grid(row=0, column=1, padx=(7,14), pady=14, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(5, weight=1)

        cab = ctk.CTkFrame(frame, fg_color="transparent")
        cab.grid(row=0, column=0, padx=20, pady=(18,4), sticky="ew")
        cab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cab, text="Clientes Cadastrados",
                     font=FONTE_TITULO, anchor="w").grid(row=0, column=0, sticky="w")
        self.lbl_total = ctk.CTkLabel(cab, text="", font=FONTE_LABEL, text_color=COR_TEXTO_SUB)
        self.lbl_total.grid(row=0, column=1, sticky="e")

        Separador(frame).grid(row=1, column=0, padx=20, pady=(0,8), sticky="ew")

        # Busca + ordem + status
        ctrl = ctk.CTkFrame(frame, fg_color="transparent")
        ctrl.grid(row=2, column=0, padx=20, pady=(0,4), sticky="ew")
        ctrl.grid_columnconfigure(0, weight=1)

        self.entry_busca = ctk.CTkEntry(
            ctrl, placeholder_text="🔍   Buscar por nome, CPF, telefone ou e-mail...",
            height=36, corner_radius=10, font=FONTE_CAMPO,
            border_width=1, border_color=COR_BORDA)
        self.entry_busca.grid(row=0, column=0, sticky="ew", padx=(0,8))
        self.entry_busca.bind("<KeyRelease>", lambda e: self._ao_buscar())
        self.entry_busca.bind("<FocusOut>",   lambda e: self._registrar_busca())

        self.opt_ordem = ctk.CTkOptionMenu(
            ctrl, values=["Mais recente","Mais antigo","Nome A-Z"],
            width=130, height=36, corner_radius=8, font=FONTE_LABEL,
            command=self._mudar_ordem)
        self.opt_ordem.grid(row=0, column=1, padx=(0,6))
        self.opt_ordem.set("Mais recente")

        self.opt_status = ctk.CTkOptionMenu(
            ctrl, values=["Todos","✅ Ativos","⏸️ Inativos"],
            width=120, height=36, corner_radius=8, font=FONTE_LABEL,
            command=self._mudar_status_filtro)
        self.opt_status.grid(row=0, column=2)
        self.opt_status.set("Todos")

        # Alfabeto
        alfa = ctk.CTkScrollableFrame(frame, fg_color="transparent",
                                      height=36, orientation="horizontal")
        alfa.grid(row=3, column=0, padx=20, pady=(0,4), sticky="ew")
        self.btns_letra = {}
        for l in ["Todos"]+list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            b = ctk.CTkButton(
                alfa, text=l, width=42 if l=="Todos" else 30, height=28,
                corner_radius=6, font=FONTE_LABEL,
                fg_color=COR_PRIMARIA if l=="Todos" else "#1E293B",
                hover_color="#2563EB",
                command=lambda x=l: self._filtrar_letra(x))
            b.pack(side="left", padx=2)
            self.btns_letra[l] = b

        # Histórico de buscas (dropdown oculto até ter buscas)
        self.frame_hist_busca = ctk.CTkFrame(frame, fg_color="transparent")
        self.frame_hist_busca.grid(row=4, column=0, padx=20, pady=(0,4), sticky="ew")
        self.frame_hist_busca.grid_columnconfigure(0, weight=1)
        self._construir_historico_busca_ui()

        # Lista rolável
        self.scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent", corner_radius=0)
        self.scroll.grid(row=5, column=0, padx=12, pady=(0,14), sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

    def _construir_historico_busca_ui(self):
        for w in self.frame_hist_busca.winfo_children():
            w.destroy()
        if not self.historico_busca:
            return
        cab = ctk.CTkFrame(self.frame_hist_busca, fg_color="transparent")
        cab.pack(fill="x")
        ctk.CTkLabel(cab, text="🕓  Buscas recentes:",
                     font=FONTE_LABEL, text_color=COR_TEXTO_SUB
                     ).pack(side="left")
        ctk.CTkButton(cab, text="Limpar", width=54, height=20,
                      corner_radius=6, font=FONTE_LABEL,
                      fg_color="#1E293B", hover_color="#263448",
                      command=self._limpar_historico_busca
                      ).pack(side="right")

        linha = ctk.CTkFrame(self.frame_hist_busca, fg_color="transparent")
        linha.pack(fill="x", pady=(2,0))
        for termo in reversed(self.historico_busca[-8:]):
            ctk.CTkButton(linha, text=termo, height=24,
                          corner_radius=6, font=FONTE_LABEL,
                          fg_color="#162032", hover_color="#1E3A5F",
                          command=lambda t=termo: self._aplicar_busca(t)
                          ).pack(side="left", padx=(0,4))

    def _ao_buscar(self):
        self._atualizar_lista()

    def _registrar_busca(self):
        termo = self.entry_busca.get().strip()
        if termo and (not self.historico_busca or self.historico_busca[-1] != termo):
            self.historico_busca.append(termo)
            if len(self.historico_busca) > MAX_HISTORICO_BUSCA:
                self.historico_busca.pop(0)
            self._construir_historico_busca_ui()

    def _aplicar_busca(self, termo):
        self.entry_busca.delete(0,"end")
        self.entry_busca.insert(0, termo)
        self._atualizar_lista()

    def _limpar_historico_busca(self):
        self.historico_busca.clear()
        self._construir_historico_busca_ui()

    # ══════════════════════════════════════════════════════════════════════════
    #  CEP
    # ══════════════════════════════════════════════════════════════════════════
    def _mask_cep_key(self, _=None):
        raw = self.entry_cep.get()
        fmt = formatar_cep(raw)
        if fmt != raw:
            pos = self.entry_cep.index("insert")
            self.entry_cep.delete(0,"end")
            self.entry_cep.insert(0, fmt)
            try: self.entry_cep.icursor(min(pos+1, len(fmt)))
            except: pass

    def _buscar_cep_auto(self):
        cep = self.entry_cep.get().strip()
        if len(re.sub(r"\D","",cep)) == 8:
            self._buscar_cep()

    def _buscar_cep(self):
        if not REQUESTS_OK:
            self.lbl_cep_status.configure(
                text="⚠️  pip install requests", text_color=COR_AMARELO)
            return
        cep = self.entry_cep.get().strip()
        self.lbl_cep_status.configure(text="🔄  Buscando...", text_color=COR_AMARELO)
        self.btn_cep.configure(state="disabled")

        def tarefa():
            dados = buscar_cep(cep)
            self.after(0, lambda: self._preencher_endereco(dados))

        threading.Thread(target=tarefa, daemon=True).start()

    def _preencher_endereco(self, dados: dict | None):
        self.btn_cep.configure(state="normal")
        if not dados:
            self.lbl_cep_status.configure(text="❌  CEP não encontrado.", text_color=COR_PERIGO)
            return
        logradouro = dados.get("logradouro","")
        bairro     = dados.get("bairro","")
        cidade     = dados.get("localidade","")
        uf         = dados.get("uf","")
        endereco   = ", ".join(p for p in [logradouro, bairro, cidade, uf] if p)
        self.entry_endereco.delete(0,"end")
        self.entry_endereco.insert(0, endereco)
        self.lbl_cep_status.configure(
            text=f"✅  {cidade} – {uf}", text_color=COR_SUCESSO)

    # ══════════════════════════════════════════════════════════════════════════
    #  LÓGICA DE CLIENTES
    # ══════════════════════════════════════════════════════════════════════════
    def _verificar_duplicatas(self, cpf, telefone, excluir_idx=None):
        avisos = []
        cpf_limpo = re.sub(r"\D","",cpf)
        tel_limpo = re.sub(r"\D","",telefone)
        for i,c in enumerate(self.clientes):
            if i == excluir_idx: continue
            if cpf_limpo and len(cpf_limpo)==11:
                if re.sub(r"\D","",c.get("cpf",""))==cpf_limpo:
                    avisos.append(f"CPF já cadastrado para: {c['nome']}")
            if tel_limpo and len(tel_limpo)>=10:
                if re.sub(r"\D","",c.get("telefone",""))==tel_limpo:
                    avisos.append(f"Telefone já cadastrado para: {c['nome']}")
        return avisos

    def _salvar_cliente(self):
        nome       = self.entry_nome.get().strip()
        cpf        = self.entry_cpf.get().strip()
        email      = self.entry_email.get().strip()
        telefone   = self.entry_telefone.get().strip()
        cep        = self.entry_cep.get().strip()
        endereco   = self.entry_endereco.get().strip()
        referencia = self.entry_referencia.get().strip()
        status     = self.var_status.get()
        obs        = self.text_obs.get("1.0","end").strip()

        if not nome or not telefone or not endereco:
            messagebox.showwarning("Campos obrigatórios",
                                   "Preencha: Nome, Telefone e Endereço.")
            return

        avisos = self._verificar_duplicatas(cpf, telefone, excluir_idx=self.idx_editando)
        if avisos:
            msg = "Atenção! Dados possivelmente duplicados:\n\n" + \
                  "\n".join(f"• {a}" for a in avisos) + \
                  "\n\nDeseja salvar mesmo assim?"
            if not messagebox.askyesno("Duplicata detectada", msg, icon="warning"):
                return

        agora = datetime.now().strftime("%d/%m/%Y %H:%M")

        if self.idx_editando is not None:
            antigo    = self.clientes[self.idx_editando]
            historico = antigo.get("historico", [])
            status_anterior = antigo.get("status","ativo")
            if status != status_anterior:
                historico.append(
                    f"Status alterado para '{status}' em {agora} por {self.usuario_logado['usuario']}")
            historico.append(
                f"Editado em {agora} por {self.usuario_logado['usuario']}")
            cliente = {
                "nome": nome, "cpf": cpf, "email": email,
                "telefone": telefone, "cep": cep,
                "endereco": endereco, "referencia": referencia,
                "status": status, "observacoes": obs,
                "cadastrado_em": antigo["cadastrado_em"],
                "historico": historico
            }
            self.clientes[self.idx_editando] = cliente
            self.idx_editando = None
            self.lbl_form_titulo.configure(text="Novo Cliente")
            self.btn_salvar.configure(text="💾   Salvar Cliente")
            self.btn_cancelar.grid_remove()
            registrar_log(self.usuario_logado["usuario"], "EDITAR", f"Cliente: {nome}")
            self._notificar("✅  Cliente atualizado!")
        else:
            cliente = {
                "nome": nome, "cpf": cpf, "email": email,
                "telefone": telefone, "cep": cep,
                "endereco": endereco, "referencia": referencia,
                "status": status, "observacoes": obs,
                "cadastrado_em": agora,
                "historico": []
            }
            self.clientes.append(cliente)
            registrar_log(self.usuario_logado["usuario"], "CADASTRAR", f"Cliente: {nome}")
            self._notificar(f"✅  '{nome}' cadastrado!")

        salvar_clientes(self.clientes)
        self._limpar()
        self._atualizar_lista()
        self._atualizar_contador_topo()
        if self.aba_atual == "dashboard":
            self._atualizar_dashboard()

    def _editar_cliente(self, idx):
        c = self.clientes[idx]
        self._limpar()
        self.entry_nome.insert(0,      c.get("nome",""))
        self.entry_cpf.insert(0,       c.get("cpf",""))
        self.entry_email.insert(0,     c.get("email",""))
        self.entry_telefone.insert(0,  c.get("telefone",""))
        self.entry_cep.insert(0,       c.get("cep",""))
        self.entry_endereco.insert(0,  c.get("endereco",""))
        self.entry_referencia.insert(0,c.get("referencia",""))
        self.var_status.set(c.get("status","ativo"))
        self.text_obs.insert("1.0",    c.get("observacoes",""))
        self.lbl_cep_status.configure(text="")
        self.idx_editando = idx
        self.lbl_form_titulo.configure(text="✏️  Editar Cliente")
        self.btn_salvar.configure(text="✏️   Atualizar Cliente")
        self.btn_cancelar.grid()
        self._mostrar_aba("clientes")

    def _alternar_status(self, idx):
        if not tem_permissao(self.usuario_logado.get("perfil","user"), "alternar_status"):
            messagebox.showwarning("Sem permissão",
                                   "Seu perfil não tem permissão para alterar o status de clientes.")
            return
        c = self.clientes[idx]
        novo = "inativo" if c.get("status","ativo")=="ativo" else "ativo"
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        c["historico"] = c.get("historico",[])
        c["historico"].append(
            f"Status alterado para '{novo}' em {agora} por {self.usuario_logado['usuario']}")
        c["status"] = novo
        salvar_clientes(self.clientes)
        registrar_log(self.usuario_logado["usuario"], "STATUS",
                      f"Cliente: {c['nome']} → {novo}")
        self._atualizar_lista()
        self._atualizar_contador_topo()
        self._notificar(f"Status de '{c['nome']}' → {novo}")

    def _excluir_cliente(self, idx):
        if not tem_permissao(self.usuario_logado.get("perfil","user"), "excluir"):
            messagebox.showwarning("Sem permissão",
                                   "Seu perfil não tem permissão para excluir clientes.")
            return
        nome = self.clientes[idx]["nome"]
        if messagebox.askyesno("Confirmar exclusão", f"Deseja excluir '{nome}'?"):
            self.clientes.pop(idx)
            salvar_clientes(self.clientes)
            registrar_log(self.usuario_logado["usuario"], "EXCLUIR", f"Cliente: {nome}")
            if self.idx_editando == idx:
                self._cancelar_edicao()
            self._atualizar_lista()
            self._atualizar_contador_topo()
            self._notificar(f"🗑️  '{nome}' removido.")

    def _ver_historico(self, idx):
        c = self.clientes[idx]
        historico = c.get("historico",[])
        linhas = [f"📅 Cadastrado em {c.get('cadastrado_em','')}"]
        linhas += [f"• {h}" for h in historico]
        messagebox.showinfo(
            f"Histórico — {c['nome']}",
            "\n".join(linhas))

    def _copiar_cliente(self, idx):
        c = self.clientes[idx]
        linhas = [
            f"Nome:      {c.get('nome','')}",
            f"CPF:       {c.get('cpf','')}",
            f"E-mail:    {c.get('email','')}",
            f"Telefone:  {c.get('telefone','')}",
            f"CEP:       {c.get('cep','')}",
            f"Endereço:  {c.get('endereco','')}",
            f"Ref.:      {c.get('referencia','')}",
        ]
        texto = "\n".join(l for l in linhas if l.split(":",1)[1].strip())
        self.clipboard_clear()
        self.clipboard_append(texto)
        self._notificar("📋  Dados copiados!")

    def _cancelar_edicao(self):
        self.idx_editando = None
        self._limpar()
        self.lbl_form_titulo.configure(text="Novo Cliente")
        self.btn_salvar.configure(text="💾   Salvar Cliente")
        self.btn_cancelar.grid_remove()

    def _limpar(self):
        for e in (self.entry_nome, self.entry_cpf, self.entry_email,
                  self.entry_telefone, self.entry_cep,
                  self.entry_endereco, self.entry_referencia):
            e.delete(0,"end")
        self.text_obs.delete("1.0","end")
        self.var_status.set("ativo")
        self.lbl_cep_status.configure(text="")

    def _mudar_ordem(self, valor):
        mapa = {"Mais recente":"recente","Mais antigo":"antigo","Nome A-Z":"nome"}
        self.ordenacao = mapa.get(valor,"recente")
        self._atualizar_lista()

    def _mudar_status_filtro(self, valor):
        mapa = {"Todos":"Todos","✅ Ativos":"ativo","⏸️ Inativos":"inativo"}
        self.filtro_status = mapa.get(valor,"Todos")
        self._atualizar_lista()

    def _filtrar_letra(self, letra):
        self.filtro_letra = letra
        for l,b in self.btns_letra.items():
            b.configure(fg_color=COR_PRIMARIA if l==letra else "#1E293B")
        self._atualizar_lista()

    # ── Lista / Cards ──────────────────────────────────────────────────────────
    def _atualizar_lista(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        busca = self.entry_busca.get().lower().strip()
        filtrados = [
            (i,c) for i,c in enumerate(self.clientes)
            if not busca or any(
                busca in str(c.get(k,"")).lower()
                for k in ("nome","cpf","telefone","email","cep"))
        ]
        if self.filtro_letra != "Todos":
            filtrados = [(i,c) for i,c in filtrados
                         if c.get("nome","").upper().startswith(self.filtro_letra)]
        if self.filtro_status != "Todos":
            filtrados = [(i,c) for i,c in filtrados
                         if c.get("status","ativo")==self.filtro_status]

        def chave(item):
            _,c = item
            if self.ordenacao=="nome": return c.get("nome","").lower()
            try:    dt = datetime.strptime(c.get("cadastrado_em",""),"%d/%m/%Y %H:%M")
            except: dt = datetime.min
            return dt if self.ordenacao=="antigo" else -dt.timestamp()
        filtrados.sort(key=chave)

        total    = len(self.clientes)
        exibidos = len(filtrados)
        self.lbl_total.configure(
            text=f"{exibidos} de {total} cliente{'s' if total!=1 else ''}")

        if not filtrados:
            ctk.CTkLabel(self.scroll, text="Nenhum cliente encontrado.",
                         text_color=COR_TEXTO_SUB, font=FONTE_CAMPO
                         ).grid(row=0, column=0, pady=40)
            return

        for linha,(idx,cliente) in enumerate(filtrados):
            self._criar_card(linha, idx, cliente)

    def _criar_card(self, linha, idx, cliente):
        status   = cliente.get("status","ativo")
        is_ativo = status == "ativo"
        cor_borda = COR_BORDA if is_ativo else "#334155"
        cor_bg    = "#162032" if is_ativo else "#111B27"

        card = ctk.CTkFrame(self.scroll, fg_color=cor_bg,
                            corner_radius=12, border_width=1, border_color=cor_borda)
        card.grid(row=linha, column=0, padx=4, pady=5, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        # Topo
        topo = ctk.CTkFrame(card, fg_color="transparent")
        topo.grid(row=0, column=0, padx=14, pady=(10,4), sticky="ew")
        topo.grid_columnconfigure(1, weight=1)

        iniciais = "".join(p[0].upper() for p in cliente["nome"].split()[:2])
        cor_avatar = COR_PRIMARIA if is_ativo else COR_INATIVO
        ctk.CTkLabel(topo, text=iniciais, width=36, height=36, corner_radius=18,
                     fg_color=cor_avatar,
                     font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
                     ).grid(row=0, column=0, sticky="w", padx=(0,10))

        nome_txt = cliente["nome"]
        cor_nome = "white" if is_ativo else COR_INATIVO
        ctk.CTkLabel(topo, text=nome_txt, font=FONTE_CARD_N,
                     text_color=cor_nome, anchor="w"
                     ).grid(row=0, column=1, sticky="w")

        # Badge status
        badge_txt = "✅ Ativo" if is_ativo else "⏸️ Inativo"
        badge_cor = "#163025" if is_ativo else "#1E293B"
        badge_tc  = COR_SUCESSO if is_ativo else COR_INATIVO
        ctk.CTkLabel(topo, text=badge_txt,
                     font=FONTE_LABEL, text_color=badge_tc,
                     fg_color=badge_cor, corner_radius=6,
                     padx=8, pady=2
                     ).grid(row=0, column=2, padx=(0,10))

        # Botões
        btns = ctk.CTkFrame(topo, fg_color="transparent")
        btns.grid(row=0, column=3, sticky="e")

        ctk.CTkButton(btns, text="📋", width=30, height=28, corner_radius=7,
                      font=FONTE_LABEL, fg_color="#1E3A5F", hover_color="#163050",
                      command=lambda i=idx: self._copiar_cliente(i)
                      ).grid(row=0, column=0, padx=(0,3))

        ctk.CTkButton(btns, text="✏️", width=30, height=28, corner_radius=7,
                      font=FONTE_LABEL, fg_color="#1E3D6B", hover_color="#163060",
                      command=lambda i=idx: self._editar_cliente(i)
                      ).grid(row=0, column=1, padx=(0,3))

        pode_toggle  = tem_permissao(self.usuario_logado.get("perfil","user"), "alternar_status")
        pode_excluir = tem_permissao(self.usuario_logado.get("perfil","user"), "excluir")

        toggle_txt = "⏸️" if is_ativo else "▶️"
        toggle_cor = "#1E3B1E" if is_ativo else "#1E2B1E"
        btn_toggle = ctk.CTkButton(btns, text=toggle_txt, width=30, height=28, corner_radius=7,
                      font=FONTE_LABEL, fg_color=toggle_cor if pode_toggle else "#1E293B",
                      hover_color="#263426" if pode_toggle else "#1E293B",
                      state="normal" if pode_toggle else "disabled",
                      command=lambda i=idx: self._alternar_status(i))
        btn_toggle.grid(row=0, column=2, padx=(0,3))

        ctk.CTkButton(btns, text="📜", width=30, height=28, corner_radius=7,
                      font=FONTE_LABEL, fg_color="#1E3B2F", hover_color="#163025",
                      command=lambda i=idx: self._ver_historico(i)
                      ).grid(row=0, column=3, padx=(0,3))

        btn_del = ctk.CTkButton(btns, text="🗑️", width=30, height=28, corner_radius=7,
                      font=FONTE_LABEL,
                      fg_color="#3B1515" if pode_excluir else "#1E293B",
                      hover_color="#5C1E1E" if pode_excluir else "#1E293B",
                      state="normal" if pode_excluir else "disabled",
                      command=lambda i=idx: self._excluir_cliente(i))
        btn_del.grid(row=0, column=4)

        # Dados
        dados = ctk.CTkFrame(card, fg_color="transparent")
        dados.grid(row=1, column=0, padx=14, pady=(0,8), sticky="ew")
        dados.grid_columnconfigure((0,1), weight=1)

        def info(icon, valor, row, col, span=1):
            if not valor: return
            ctk.CTkLabel(dados, text=f"{icon} {valor}",
                         font=FONTE_CARD_D, text_color=COR_TEXTO_SUB,
                         anchor="w", wraplength=260
                         ).grid(row=row, column=col, columnspan=span,
                                padx=(0,8), pady=1, sticky="w")

        info("📞", cliente.get("telefone"),         0, 0)
        info("🪪",  cliente.get("cpf"),              0, 1)
        info("✉️",  cliente.get("email"),            1, 0, 2)
        cep_end = " ".join(filter(None,[cliente.get("cep",""), cliente.get("endereco","")]))
        info("📍", cep_end or cliente.get("endereco"), 2, 0, 2)
        info("🏷️", cliente.get("referencia"),       3, 0, 2)

        obs = cliente.get("observacoes","")
        if obs:
            Separador(card).grid(row=2, column=0, padx=14, pady=(0,4), sticky="ew")
            ctk.CTkLabel(card, text=f"📝  {obs}",
                         font=FONTE_LABEL, text_color="#64748B",
                         anchor="w", wraplength=420, justify="left"
                         ).grid(row=3, column=0, padx=14, pady=(0,6), sticky="w")

        historico = cliente.get("historico",[])
        rodape = f"Cadastrado em {cliente.get('cadastrado_em','')}"
        if historico:
            rodape += f"   •   {historico[-1]}"
        ctk.CTkLabel(card, text=rodape,
                     font=FONTE_LABEL, text_color="#3B4A60", anchor="e"
                     ).grid(row=4, column=0, padx=14, pady=(0,8), sticky="e")

    # ══════════════════════════════════════════════════════════════════════════
    #  LOG DE AÇÕES
    # ══════════════════════════════════════════════════════════════════════════
    def _ver_log(self):
        win = ctk.CTkToplevel(self)
        win.title("📋  Log de Ações")
        win.geometry("760x520")
        win.configure(fg_color=COR_FUNDO)
        win.grab_set()

        topo = ctk.CTkFrame(win, fg_color=COR_CARD, corner_radius=0, height=52)
        topo.pack(fill="x")
        topo.pack_propagate(False)
        topo.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(topo, text="📋  Log de Ações do Sistema",
                     font=FONTE_TITULO).pack(side="left", padx=20, pady=12)

        # Filtro por usuário
        dados_u = carregar_usuarios()
        usuarios = ["Todos"] + [u["usuario"] for u in dados_u.get("usuarios",[])]
        self._log_filtro_usuario = ctk.StringVar(value="Todos")
        opt = ctk.CTkOptionMenu(topo, values=usuarios, width=140, height=32,
                                variable=self._log_filtro_usuario,
                                command=lambda _: _recarregar())
        opt.pack(side="right", padx=20, pady=10)
        ctk.CTkLabel(topo, text="Filtrar:", font=FONTE_LABEL,
                     text_color=COR_TEXTO_SUB).pack(side="right", pady=10)

        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=14, pady=14)
        scroll.grid_columnconfigure(0, weight=1)

        CORES_ACAO = {
            "LOGIN":    "#1E3D6B",
            "CADASTRAR":"#163025",
            "EDITAR":   "#1E3A1E",
            "EXCLUIR":  "#3B1515",
            "STATUS":   "#2A2A0A",
        }

        def _recarregar():
            for w in scroll.winfo_children():
                w.destroy()
            log = carregar_log()
            filtro = self._log_filtro_usuario.get()
            if filtro != "Todos":
                log = [e for e in log if e.get("usuario","") == filtro]
            log_rev = list(reversed(log))
            if not log_rev:
                ctk.CTkLabel(scroll, text="Nenhuma ação registrada.",
                             font=FONTE_CAMPO, text_color=COR_TEXTO_SUB
                             ).grid(row=0, column=0, pady=40)
                return
            for i, entrada in enumerate(log_rev):
                acao   = entrada.get("acao","")
                cor_bg = CORES_ACAO.get(acao, "#1E293B")
                row_f  = ctk.CTkFrame(scroll, fg_color=cor_bg,
                                      corner_radius=8, border_width=1,
                                      border_color=COR_BORDA)
                row_f.grid(row=i, column=0, padx=4, pady=3, sticky="ew")
                row_f.grid_columnconfigure(2, weight=1)

                ctk.CTkLabel(row_f,
                             text=entrada.get("data_hora",""),
                             font=FONTE_LABEL, text_color=COR_TEXTO_SUB, width=140
                             ).grid(row=0, column=0, padx=(10,6), pady=6, sticky="w")

                ctk.CTkLabel(row_f,
                             text=f"👤 {entrada.get('usuario','')}",
                             font=FONTE_SECAO, width=100
                             ).grid(row=0, column=1, padx=(0,6), pady=6, sticky="w")

                ctk.CTkLabel(row_f,
                             text=f"[{acao}]  {entrada.get('detalhe','')}",
                             font=FONTE_CARD_D, text_color=COR_TEXTO_SUB,
                             anchor="w"
                             ).grid(row=0, column=2, padx=(0,10), pady=6, sticky="w")

        _recarregar()

    # ══════════════════════════════════════════════════════════════════════════
    #  GERENCIAR USUÁRIOS (admin)
    # ══════════════════════════════════════════════════════════════════════════
    def _gerenciar_usuarios(self):
        win = ctk.CTkToplevel(self)
        win.title("Gerenciar Usuários")
        win.geometry("520x560")
        win.configure(fg_color=COR_FUNDO)
        win.grab_set()

        dados_u = carregar_usuarios()

        frame_lista = ctk.CTkScrollableFrame(win, fg_color=COR_CARD, corner_radius=14)
        frame_lista.pack(fill="both", expand=True, padx=14, pady=(14,6))
        frame_lista.grid_columnconfigure(0, weight=1)

        def recarregar():
            for w in frame_lista.winfo_children():
                w.destroy()
            d = carregar_usuarios()
            ctk.CTkLabel(frame_lista, text="👥  Usuários cadastrados",
                         font=FONTE_SECAO, anchor="w"
                         ).grid(row=0, column=0, padx=14, pady=(12,8), sticky="w")
            for i, u in enumerate(d.get("usuarios",[])):
                row_f = ctk.CTkFrame(frame_lista, fg_color="#162032",
                                     corner_radius=8, border_width=1, border_color=COR_BORDA)
                row_f.grid(row=i+1, column=0, padx=8, pady=3, sticky="ew")
                row_f.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(row_f,
                             text=f"👤  {u['usuario']}   [{u.get('perfil','user')}]   — criado em {u.get('criado_em','')}",
                             font=FONTE_CARD_D, anchor="w"
                             ).grid(row=0, column=0, padx=10, pady=8, sticky="w")
                if u["usuario"].lower() != "admin":
                    ctk.CTkButton(row_f, text="🗑️", width=30, height=28,
                                  corner_radius=6, font=FONTE_LABEL,
                                  fg_color="#3B1515", hover_color="#5C1E1E",
                                  command=lambda nome=u["usuario"]: remover_usuario(nome)
                                  ).grid(row=0, column=1, padx=8, pady=8)

        def remover_usuario(nome):
            if not messagebox.askyesno("Remover usuário",
                                       f"Deseja remover o usuário '{nome}'?"):
                return
            d = carregar_usuarios()
            d["usuarios"] = [u for u in d["usuarios"] if u["usuario"].lower()!=nome.lower()]
            salvar_usuarios(d)
            registrar_log(self.usuario_logado["usuario"], "REMOVER_USUARIO", f"Usuário: {nome}")
            recarregar()

        recarregar()

        # Formulário novo usuário
        form = ctk.CTkFrame(win, fg_color=COR_CARD, corner_radius=14)
        form.pack(fill="x", padx=14, pady=(0,14))
        form.grid_columnconfigure((0,1,2), weight=1)

        ctk.CTkLabel(form, text="➕  Novo Usuário", font=FONTE_SECAO
                     ).grid(row=0, column=0, columnspan=3, padx=14, pady=(12,8), sticky="w")

        e_user = ctk.CTkEntry(form, placeholder_text="Usuário", height=36,
                              corner_radius=8, font=FONTE_CAMPO,
                              border_width=1, border_color=COR_BORDA)
        e_user.grid(row=1, column=0, padx=(14,6), pady=(0,12), sticky="ew")

        e_pass = ctk.CTkEntry(form, placeholder_text="Senha", show="●", height=36,
                              corner_radius=8, font=FONTE_CAMPO,
                              border_width=1, border_color=COR_BORDA)
        e_pass.grid(row=1, column=1, padx=(0,6), pady=(0,12), sticky="ew")

        opt_perfil = ctk.CTkOptionMenu(form, values=["user","admin"],
                                       width=100, height=36, corner_radius=8, font=FONTE_LABEL)
        opt_perfil.grid(row=1, column=2, padx=(0,14), pady=(0,12))
        opt_perfil.set("user")

        lbl_err_u = ctk.CTkLabel(form, text="", font=FONTE_LABEL, text_color=COR_PERIGO)
        lbl_err_u.grid(row=2, column=0, columnspan=3, padx=14, pady=(0,4))

        def adicionar():
            usuario = e_user.get().strip()
            senha   = e_pass.get()
            perfil  = opt_perfil.get()
            if not usuario or not senha:
                lbl_err_u.configure(text="❌  Preencha usuário e senha.")
                return
            if len(senha) < 4:
                lbl_err_u.configure(text="❌  Senha mínima: 4 caracteres.")
                return
            d = carregar_usuarios()
            if any(u["usuario"].lower()==usuario.lower() for u in d["usuarios"]):
                lbl_err_u.configure(text="❌  Usuário já existe.")
                return
            d["usuarios"].append({
                "usuario": usuario, "senha_hash": hash_senha(senha),
                "perfil": perfil,
                "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M")
            })
            salvar_usuarios(d)
            registrar_log(self.usuario_logado["usuario"], "CRIAR_USUARIO",
                          f"Usuário: {usuario}  perfil: {perfil}")
            e_user.delete(0,"end")
            e_pass.delete(0,"end")
            lbl_err_u.configure(text="")
            recarregar()
            self._notificar(f"✅  Usuário '{usuario}' criado!")

        ctk.CTkButton(form, text="Adicionar Usuário", height=38, corner_radius=10,
                      font=FONTE_SECAO, fg_color=COR_PRIMARIA, hover_color="#2563EB",
                      command=adicionar
                      ).grid(row=3, column=0, columnspan=3, padx=14, pady=(0,14), sticky="ew")

    # ══════════════════════════════════════════════════════════════════════════
    #  UTILITÁRIOS
    # ══════════════════════════════════════════════════════════════════════════
    def _formulario_preenchido(self):
        if any(e.get().strip() for e in (self.entry_nome, self.entry_cpf, self.entry_email,
                                          self.entry_telefone, self.entry_cep,
                                          self.entry_endereco, self.entry_referencia)):
            return True
        return bool(self.text_obs.get("1.0","end").strip())

    def _confirmar_fechar(self):
        if self._formulario_preenchido():
            if not messagebox.askyesno("Sair sem salvar?",
                                       "Há dados no formulário não salvos.\nDeseja sair mesmo assim?",
                                       icon="warning"):
                return
        self.destroy()

    def _atualizar_contador_topo(self):
        total = len(self.clientes)
        self.lbl_contador_topo.configure(
            text=f"👥 {total} cliente{'s' if total!=1 else ''}")

    def _notificar(self, msg):
        self.lbl_notif.configure(text=msg)
        if self._notif_job:
            self.after_cancel(self._notif_job)
        self._notif_job = self.after(3500, lambda: self.lbl_notif.configure(text=""))

    def _mask_cpf(self, _=None):
        raw = self.entry_cpf.get()
        fmt = formatar_cpf(raw)
        if fmt != raw:
            pos = self.entry_cpf.index("insert")
            self.entry_cpf.delete(0,"end")
            self.entry_cpf.insert(0,fmt)
            try: self.entry_cpf.icursor(min(pos+1,len(fmt)))
            except: pass

    def _mask_tel(self, _=None):
        raw = self.entry_telefone.get()
        fmt = formatar_telefone(raw)
        if fmt != raw:
            pos = self.entry_telefone.index("insert")
            self.entry_telefone.delete(0,"end")
            self.entry_telefone.insert(0,fmt)
            try: self.entry_telefone.icursor(min(pos+1,len(fmt)))
            except: pass


# ══════════════════════════════════════════════════════════════════════════════
#  PONTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    login = TelaLogin()
    login.mainloop()
    if login.usuario_logado:
        app = App(login.usuario_logado)
        app.mainloop()