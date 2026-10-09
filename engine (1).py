import csv, hashlib, json, re, sqlite3, unicodedata
from pathlib import Path
import fitz

DB="auditoria.sqlite3"
ENGINE_VERSION="3.0-linhas-e-exercicios"
KEYWORDS={"RETIFICACAO":r"RETIFIC|ONDE CONSTA|PASSE A CONSTAR|CORRIG",
          "INCLUSAO":r"INCLU[SÍI]|INCLUIR|ACRESCENT",
          "ANULACAO":r"ANULA|TORNAR SEM EFEITO|DESCONSIDER|EXCLUIR|CANCELA"}
YEARS=re.compile(r"\b20(?:19|20|21|22|23|24|25)\b")
MAT=re.compile(r"(?<!\d)\d{7,11}(?!\d)")
def normalize(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(s).upper()) if not unicodedata.combining(c))
def connect():
    con=sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS docs (id TEXT PRIMARY KEY, name TEXT, numero INTEGER, tipo TEXT, pages INTEGER DEFAULT 0, done_pages INTEGER DEFAULT 0, status TEXT DEFAULT 'PENDENTE', error TEXT DEFAULT '')")
    con.execute("CREATE TABLE IF NOT EXISTS hits (doc TEXT, page INTEGER, tipo TEXT, matricula TEXT, servidor TEXT, exercicio TEXT, base_valor TEXT, trecho TEXT, situacao TEXT DEFAULT 'CANDIDATO - REVISAR', UNIQUE(doc,page,tipo,matricula,exercicio,trecho))")
    con.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    version=con.execute("SELECT value FROM meta WHERE key='engine_version'").fetchone()
    if version is None or version[0]!=ENGINE_VERSION:
        # Candidatos antigos são inválidos; não reaproveitar resultados da heurística anterior.
        con.execute("DELETE FROM hits")
        con.execute("DELETE FROM docs")
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES ('engine_version',?)",(ENGINE_VERSION,))
    con.commit()
    return con
def identity(path):
    name=path.name
    m=re.search(r"(?<!\d)(1[012][.\s]?\d{3})(?!\d)",name)
    num=int(re.sub(r"\D","",m.group(1))) if m else 99999
    typ='SUPLEMENTO' if re.search('SUP',name,re.I) else ('EXTRA' if re.search('EXTRA',name,re.I) else 'PRINCIPAL')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    return digest,num,typ
def load_base_csv(path):
    """Carrega CSV Excel (UTF-8, UTF-16, Windows-1252) sem modificar a base."""
    import io
    path=Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Base Geral não encontrada: {path}")
    raw=path.read_bytes()
    if not raw:
        raise ValueError("Arquivo CSV da Base Geral está vazio")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings=("utf-16",)
    elif raw.startswith(b"\xef\xbb\xbf"):
        encodings=("utf-8-sig",)
    else:
        encodings=("utf-8-sig", "cp1252", "latin-1")
    content=None
    for encoding in encodings:
        try:
            content=raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        raise ValueError("Não foi possível identificar a codificação do CSV")
    # Excel brasileiro costuma usar ;, mas também aceita , e tab.
    header=next((line for line in content.splitlines() if line.strip()), "")
    delimiter=max((";", ",", "\t"), key=header.count)
    if delimiter not in header:
        raise ValueError("Separador do CSV não identificado")
    reader=csv.DictReader(io.StringIO(content, newline=""), delimiter=delimiter)
    headers={normalize(h).strip().lstrip("\ufeff") for h in (reader.fieldnames or []) if h}
    if not {"MATRICULA", "SERVIDOR"}.issubset(headers):
        raise ValueError("CSV inválido: abra a aba Base Geral antes de salvar; colunas MATRÍCULA e SERVIDOR são obrigatórias")
    data={}
    for row in reader:
        normalized={normalize(k).strip():v for k,v in row.items() if k}
        mat=re.sub(r"\D", "", normalized.get("MATRICULA", "") or "")
        if mat:
            data[mat]=normalized
    if not data:
        raise ValueError("Nenhuma matrícula válida foi encontrada no CSV")
    return data
# A versão 3 prioriza precisão: candidatos sem exercício confiável ficam
# INDETERMINADO e nenhum valor é declarado como correção confirmada.
ADI_CONTEXT=re.compile(r"AVALIACAO\\s+(?:DE\\s+)?DESEMPENHO|\\bADI\\b|\\bPGDI\\b|NOTAS?\\s+(?:DA\\s+)?AVALIACAO|RESULTADO\\s+(?:DA\\s+)?AVALIACAO")
NEGATIVE=re.compile(r"ORCAMENTARI|CONTRATO|LICITACAO|EMPENHO|PREGAO|TERMO ADITIVO")
SCORE=re.compile(r"(?<!\\d)(?:100(?:[,.]00)?|[1-9]?\\d[,.]\\d{1,2}|\\bC\\d{3}\\b)(?!\\d)")
YEAR_CONTEXT=re.compile(r"(?:EXERCICIO|ANO\\s+(?:DE\\s+)?AVALIACAO|ADI\\s+(?:DE\\s+)?|AVALIACAO\\s+(?:DE\\s+)?DESEMPENHO\\s+(?:DE\\s+)?)(?:\\s*[:\\-]?\\s*)(20(?:19|20|21|22|23|24|25))\\b")
def year_from_header(lines):
    found=set()
    for line in lines:
        for y in YEAR_CONTEXT.findall(line):
            found.add(y)
    return next(iter(found)) if len(found)==1 else 'INDETERMINADO'
def row_candidates(page,base):
    """Produz somente linhas candidatas com identidade e contexto da mesma seção.

    Extrair texto de PDF pode embaralhar colunas: uma matrícula na página
    não prova que a nota vizinha lhe pertence. Por isso, valores permanecem
    apenas na evidência, sem preencher automaticamente 'nota nova'.
    """
    lines=[x.strip() for x in page.get_text(sort=True).splitlines() if x.strip()]
    norms=[normalize(x) for x in lines]
    section_start=0
    section_adi=False
    section_kind=None
    section_year='INDETERMINADO'
    for j,line in enumerate(norms):
        # Cabeçalho de ato redefine o contexto, evitando herdar retificação
        # de ato anterior na mesma página.
        if re.search(r"^(?:EDITAL|RESOLUCAO|PORTARIA|DECRETO|EXTRATO|AVISO|DESPACHO|TERMO)\\b",line):
            section_start=j
            section_adi=False
            section_kind=None
            section_year='INDETERMINADO'
        if ADI_CONTEXT.search(line):
            section_adi=True
        for kind,pattern in KEYWORDS.items():
            if re.search(pattern,line) and (j-section_start)<100:
                section_kind=kind
                break
        if j-section_start<60:
            header_year=year_from_header(norms[section_start:j+1])
            if header_year!='INDETERMINADO':
                section_year=header_year
        if not section_adi or not section_kind:
            continue
        if NEGATIVE.search(line):
            continue
        mats=[m for m in MAT.findall(line) if m in base]
        if not mats:
            continue
        # Não atribuir números de um registro a outro: matrícula isolada
        # é candidato à revisão, nunca divergência confirmada.
        for mat in dict.fromkeys(mats):
            rec=base[mat]
            name=normalize(rec.get('SERVIDOR',''))
            if not name:
                continue
            # Nome na linha é forte evidência; caso contrário buscar só a
            # linha imediatamente adjacente, sinalizando revisão no trecho.
            row=' '.join(norms[j:min(len(norms),j+2)])
            tokens=[w for w in name.split() if len(w)>2]
            matched=sum(1 for w in tokens if re.search(r'(?<!\\w)'+re.escape(w)+r'(?!\\w)',row))
            if matched<min(2,len(tokens)):
                continue
            # Um trecho nunca deve conter outra matrícula da base, porque
            # indicaria duas linhas da tabela fundidas.
            local=norms[j]
            if len(set(m for m in MAT.findall(local) if m in base))>1:
                continue
            year=section_year
            # Ano explicitamente rotulado na mesma linha pode resolver
            # cabeçalho ausente, mas anos avulsos não.
            local_year=year_from_header([local])
            if local_year!='INDETERMINADO':
                year=local_year
            excerpt=' | '.join(lines[max(section_start,j-1):min(len(lines),j+2)])[:1400]
            yield section_kind,mat,rec.get('SERVIDOR',''),year,rec.get('NOTA '+year,'') if year!='INDETERMINADO' else '',excerpt
def scan_one(path,base):
    con=connect()
    digest,num,typ=identity(path)
    old=con.execute("SELECT status,done_pages FROM docs WHERE id=?",(digest,)).fetchone()
    if old and old[0] in ('CONCLUIDO','EXTRACAO CONCLUIDA - REVISAR'):
        con.close()
        return 'já extraído; pendente de validação'
    con.execute("INSERT OR IGNORE INTO docs (id,name,numero,tipo) VALUES (?,?,?,?)",(digest,path.name,num,typ))
    con.commit()
    try:
        with fitz.open(path) as pdf:
            count=len(pdf)
            con.execute("UPDATE docs SET pages=?,status='EM ANALISE',error='' WHERE id=?",(count,digest))
            con.commit()
            start=old[1] if old else 0
            for i in range(start,count):
                for kind,mat,name,year,value,excerpt in row_candidates(pdf[i],base):
                    con.execute("INSERT OR IGNORE INTO hits(doc,page,tipo,matricula,servidor,exercicio,base_valor,trecho) VALUES(?,?,?,?,?,?,?,?)",
                                (digest,i+1,kind,mat,name,year,str(value),excerpt))
                con.execute("UPDATE docs SET done_pages=? WHERE id=?",(i+1,digest))
                con.commit()
            con.execute("UPDATE docs SET status='EXTRACAO CONCLUIDA - REVISAR' WHERE id=?",(digest,))
            con.commit()
        return 'extração concluída, pendente de validação'
    except Exception as e:
        con.execute("UPDATE docs SET status='ERRO',error=? WHERE id=?",(str(e),digest))
        con.commit()
        return f'erro: {e}'
    finally:
        con.close()
def run_folder(folder,base_csv):
    paths=sorted(Path(folder).glob('*.pdf'),key=lambda p:(identity(p)[1],0 if identity(p)[2]=='PRINCIPAL' else 1,p.name))
    base=load_base_csv(base_csv)
    seen=set()
    for path in paths:
        h,_,_=identity(path)
        if h in seen:continue
        seen.add(h)
        yield path.name,scan_one(path,base)
