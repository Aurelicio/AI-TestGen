import os
import json
import asyncio
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
from google import genai
from dotenv import load_dotenv

class CasoDeTeste(BaseModel):
    id: str
    descricao: str
    classe_equivalencia: str
    dados_entrada: str
    resultado_esperado: str
    tipo: str

class ListaTestes(BaseModel):
    variaveis_identificadas: List[str]
    casos_de_teste: List[CasoDeTeste]

USAR_PROMPT_CHAINING = True

modelo_llm = "gemma-4-31b-it"  

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("ERRO: GOOGLE_API_KEY não foi definida no arquivo .env")
client = genai.Client(api_key=api_key)
app = FastAPI()


async def call_llm_with_retry(prompt: str, max_retries: int = 3, inicial_delay: int = 2):
    """
    
    Args:
        prompt: Conteúdo do prompt
        max_retries: Número máximo de tentativas
        inicial_delay: Delay inicial em segundos
    
    Returns:
        Resposta da API ou None se falhar
    """
    for tentativa in range(max_retries):
        try:
            print(f"[LLM CALL] Tentativa {tentativa + 1}/{max_retries}")
            print(f"[LLM DEBUG] Modelo: {modelo_llm}")
            
            resposta = client.models.generate_content(
                model=modelo_llm,
                contents=prompt
            )
            
            # Verifica se a resposta tem conteúdo válido
            if resposta and hasattr(resposta, 'text') and resposta.text:
                print(f"[LLM SUCCESS] Resposta recebida na tentativa {tentativa + 1}")
                return resposta
            else:
                print(f"[LLM WARNING] Resposta vazia ou inválida na tentativa {tentativa + 1}")
                print(f"[LLM DEBUG] Resposta obj: {resposta}")
                if tentativa < max_retries - 1:
                    delay = inicial_delay * (2 ** tentativa)
                    print(f"[LLM RETRY] Aguardando {delay}s antes de tentar novamente...")
                    await asyncio.sleep(delay)
                    
        except Exception as e:
            erro_str = str(e)
            erro_tipo = type(e).__name__
            print(f"[LLM ERROR] Tentativa {tentativa + 1} falhou com erro: {erro_tipo} - {erro_str}")
            print(f"[LLM DEBUG] Exception completa: {repr(e)}")
            
            # Se for erro 500 ou similar, tenta novamente
            if tentativa < max_retries - 1:
                delay = inicial_delay * (2 ** tentativa)
                print(f"[LLM RETRY] Aguardando {delay}s antes de tentar novamente...")
                await asyncio.sleep(delay)
            else:
                print(f"[LLM FATAL] Falha permanente após {max_retries} tentativas")
                raise
    
    return None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class EstoriaRequest(BaseModel):
    estoria: str

@app.post("/api/generate-tests")
async def generate_tests(request: EstoriaRequest):
    try:
        diretorio_atual = os.path.dirname(os.path.abspath(__file__))
        caminho_arquivo = os.path.join(diretorio_atual, "instrucoes_qa.txt")
        
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            treinamento_qa = f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail=f"ERRO DE SISTEMA: O arquivo 'instrucoes_qa.txt' não foi encontrado no caminho: {caminho_arquivo}")

    try:
        conteudo_limpo = request.estoria.strip()
        
        if len(conteudo_limpo) < 100:
            mensagem_fixa = f"""A entrada está muito curta. Por favor, forneça uma estória estruturada.

Template esperado:

**Título:** [Descreva a funcionalidade de forma concisa]
**Como um** [tipo de usuário],
**Eu quero** [objetivo],
**Para que** [benefício].
**Detalhamento:** [Informações adicionais]
**Critérios de Aceitação:**
- Regra 1: [Com limite numérico ou tamanho mensurável]
- Regra 2: [Com limite numérico ou tamanho mensurável]
..."""

            return {
                "variaveis_identificadas": [],
                "casos_de_teste": [],
                "erro_validacao": mensagem_fixa
            }

        # ETAPA 1 - Validação 

        prompt_etapa1 = f"""
        {treinamento_qa}

        === TAREFA ATUAL ===
        Analise a seguinte entrada fornecida pelo usuário:
        "{conteudo_limpo}"

        1. VERIFICAÇÃO DA ESTRUTURA E LITERAL:
           Você está PROIBIDO de deduzir a estrutura pelo contexto. Você deve agir como um analisador sintático cego. 
           Verifique se o texto contém as seguintes DECLARAÇÕES EXPLÍCITAS:
           - "titulo": Possui um título ou nome para a funcionalidade?
           - "stakeholder": O texto contém a sintaxe exata declarando o papel logo no início? (Ex: "Como um [papel]", "Sendo um [papel]"). Se não for localizado no texto o trecho "Como um" informando claramente qual tipo de usuário, você DEVE marcar "ausente" SEMPRE. NÃO DEVE deduzir o stakeholder baseando-se no título ou em palavras separadas no resto do texto.
           - "problema": O texto declara a ação que o ator deseja realizar? (ex: "desejo cadastrar", "quero acessar").
           - "beneficio": O texto declara o porquê ou valor de negócio final? (ex: "para poder...", "com o objetivo de...").
           - "detalhamento": Possui contexto adicional ou regras descritivas?
           - "criterios_aceitacao": Possui critérios de aceitação CLAROS e TESTÁVEIS? (numéricos ou descritivos)
           - "criterios_aceitacao_mensuraveis": Possui regras com limites numéricos, intervalos ou tamanhos verificáveis? (pode estar ausente mesmo que a estória seja válida)

        2. REGRA DE STATUS:
           A estória é "valido" SE tiver: titulo, stakeholder, problema, beneficio, detalhamento E criterios_aceitacao (não pode ser vago/subjetivo).
           A estória é "invalido" SE: faltarem items estruturais OR os critérios de aceitação forem muito subjetivos/intestáveis.
           O campo "criterios_aceitacao_mensuraveis" é informativo (pode estar ausente mesmo que a estória seja válida).

        3. DETERMINAÇÃO DA TÉCNICA:
           - Se "criterios_aceitacao_mensuraveis" = "presente": usar "tecnica_aplicada": "Particionamento de Equivalência + Análise de Valor Limite"
           - Se "criterios_aceitacao_mensuraveis" = "ausente" mas "criterios_aceitacao" = "presente": usar "tecnica_aplicada": "Testes Descritivos Baseados em Critérios (sem análise de valor limite)"

        Responda APENAS com um JSON puro neste formato:
        {{
            "auditoria_checklist": {{
                "titulo": "presente" ou "ausente",
                "stakeholder": "presente" ou "ausente",
                "problema": "presente" ou "ausente",
                "beneficio": "presente" ou "ausente",
                "detalhamento": "presente" ou "ausente",
                "criterios_aceitacao": "presente" ou "ausente",
                "criterios_aceitacao_mensuraveis": "presente" ou "ausente"
            }},
            "status": "valido" ou "invalido",
            "mensagem_erro": "Se invalido, descreva brevemente o motivo.",
            "variaveis_identificadas": ["lista das variáveis numéricas/tamanhos encontrados, vazio se não houver"],
            "tecnica_aplicada": "Particionamento de Equivalência + Análise de Valor Limite" ou "Testes Descritivos Baseados em Critérios (sem análise de valor limite)" ou "Nenhuma",
            "analise_classes": "Detalhe da análise de classes e técnicas aplicadas, baseado nos exemplos."
        }}
        """

        resposta_etapa1 = client.models.generate_content(
            model=modelo_llm,
            contents=prompt_etapa1
        )
        
        texto_etapa1 = resposta_etapa1.text.replace("```json", "").replace("```", "").strip()
        
        try:
            dados_analise = json.loads(texto_etapa1)
            
            # Montagem da mensagem de erro (APENAS se status for invalido)
            if dados_analise.get("status") == "invalido":
                checklist = dados_analise.get("auditoria_checklist", {})
                
                # Mapeamento para nomes na interface
                mapa_nomes = {
                    "titulo": "'Título'",
                    "stakeholder": "'Stakeholder (Como um...)'",
                    "problema": "'Problema (Eu quero...)'",
                    "beneficio": "'Benefício (Para...)'",
                    "detalhamento": "'Detalhamento'",
                    "criterios_aceitacao": "'Critérios de Aceitação'",
                    "criterios_aceitacao_mensuraveis": "'Critérios de Aceitação (com limites mensuráveis)'"
                }
                
                # Coleta dos itens que a IA marcou como "ausente"
                itens_ausentes = [mapa_nomes.get(k, k) for k, v in checklist.items() if v == "ausente"]
                texto_ausentes = ", ".join(itens_ausentes) if itens_ausentes else "Itens obrigatórios não detectados"
                
                # Mensagem da IA + template esperado
                mensagem_ia = dados_analise.get("mensagem_erro", "")
                mensagem_fixa = f"""A estória está incompleta ou possui critérios não testáveis.

Motivo: {mensagem_ia}
Itens faltando/inválidos: {texto_ausentes}.

Template esperado:

**Título:** [Descreva a funcionalidade de forma concisa]
**Como um** [tipo de usuário],
**Eu quero** [objetivo],
**Para que** [benefício].
**Detalhamento:** [Informações adicionais]
**Critérios de Aceitação:**
- Regra 1: [Critério testável, com ou sem limite numérico]
- Regra 2: [Critério testável, com ou sem limite numérico]
..."""

                return {
                    "variaveis_identificadas": [],
                    "casos_de_teste": [],
                    "tecnica_aplicada": "Nenhuma",
                    "erro_validacao": mensagem_fixa
                }
                
        except json.JSONDecodeError:
            dados_analise = {"variaveis_identificadas": [], "analise_classes": texto_etapa1, "tecnica_aplicada": "Nenhuma"}

        # ETAPA 2: Montagem dos Casos de Teste

        prompt_etapa2 = f"""
        Atue como Analista de QA.
        
        Estória Original: "{conteudo_limpo}"
        Técnica Aplicada: {json.dumps(dados_analise.get("tecnica_aplicada", "Nenhuma"))}
        Análise Prévia: {json.dumps(dados_analise.get("analise_classes", ""))}

        INSTRUÇÕES ESPECÍFICAS:
        
        1. SE a técnica for "Particionamento de Equivalência + Análise de Valor Limite":
           - Crie Casos de Teste englobando os valores limites (Limite exato, Limite-1, Limite+1)
           - Inclua classes válidas e inválidas conforme documentado na análise prévia
           - Cada limite numérico deve ter testes para: valor limite inferior, inferior-1, superior, superior+1
        
        2. SE a técnica for "Testes Descritivos Baseados em Critérios":
           - Crie Casos de Teste derivados dos critérios de aceitação descritivos
           - Mapear cenários positivos (que atendem aos critérios) e negativos (que violam os critérios)
           - Não aplique análise de valor limite (critérios não têm valores numéricos mensuráveis)

        Responda ESTRITAMENTE com o JSON no formato abaixo, sem textos explicativos:
        {{
            "variaveis_identificadas": {json.dumps(dados_analise.get("variaveis_identificadas", []))},
            "tecnica_aplicada": "{dados_analise.get('tecnica_aplicada', 'Nenhuma')}",
            "casos_de_teste": [
                {{
                    "id": "CT01",
                    "descricao": "string explicativa",
                    "classe_equivalencia": "Ex: Valor Limite Inferior Válido ou Cenário Positivo com Alfanumérico",
                    "dados_entrada": "O valor exato a ser inserido",
                    "resultado_esperado": "Comportamento esperado do sistema",
                    "tipo": "Positivo ou Negativo"
                }}
            ],
            "erro_validacao": ""
        }}
        """

        resposta_etapa2 = client.models.generate_content(
            model=modelo_llm,
            contents=prompt_etapa2
        )

        texto_etapa2 = resposta_etapa2.text.replace("```json", "").replace("```", "").strip()
        
        try:
            dados_saida = json.loads(texto_etapa2)
            
            if "variaveis_identificadas" not in dados_saida: 
                dados_saida["variaveis_identificadas"] = dados_analise.get("variaveis_identificadas", [])
            if "casos_de_teste" not in dados_saida: 
                dados_saida["casos_de_teste"] = []
            if "tecnica_aplicada" not in dados_saida:
                dados_saida["tecnica_aplicada"] = dados_analise.get("tecnica_aplicada", "Nenhuma")
                
            return dados_saida

        except json.JSONDecodeError:
            return {
                "variaveis_identificadas": [],
                "casos_de_teste": [],
                "tecnica_aplicada": dados_analise.get("tecnica_aplicada", "Nenhuma"),
                "erro_validacao": "Erro de processamento na Etapa de Síntese."
            }

    except Exception as e:
        # Se for um erro da IA da Google (ex: 400 Bad Request por causa dos "aaaa"), 
        # ele vai mostrar o erro exato na tela agora.
        print(f"Erro Crítico no Servidor: {e}")
        raise HTTPException(status_code=500, detail=f"Falha na IA da Google: {str(e)}")


@app.post("/api/generate-tests-stream")
async def generate_tests_stream(request: EstoriaRequest):
    """
    Endpoint com Server-Sent Events (SSE) que envia progresso de cada etapa em tempo real.
    Pode usar prompt chaining (4 etapas) ou uma única requisição, conforme USAR_PROMPT_CHAINING.
    """
    if USAR_PROMPT_CHAINING:
        return await _gerar_tests_com_prompt_chaining(request)
    else:
        return await _gerar_tests_sem_prompt_chaining(request)


async def _gerar_tests_sem_prompt_chaining(request: EstoriaRequest):
    """
    Abordagem SEM prompt chaining: uma requisição direta e simples.
    SEM treinamento prévio, SEM exemplos (few shot), SEM etapas cognitivas.
    Apenas: estória e geração de casos de teste no formato esperado.
    
    Não exibe as 4 etapas na interface. Apenas processamento direto.
    """
    async def event_generator():
        try:
            conteudo_limpo = request.estoria.strip()
            
            # Validação de tamanho mínimo
            if len(conteudo_limpo) < 100:
                mensagem_fixa = """A entrada está muito curta. Por favor, forneça uma estória estruturada.

Template esperado:

**Título:** [Descreva a funcionalidade de forma concisa]
**Como um** [tipo de usuário],
**Eu quero** [objetivo],
**Para que** [benefício].
**Detalhamento:** [Informações adicionais]
**Critérios de Aceitação:**
- Regra 1: [Com limite numérico ou tamanho mensurável]
- Regra 2: [Com limite numérico ou tamanho mensurável]
..."""
                
                yield f'data: {json.dumps({"tipo": "validacao_tamanho", "status": "falha", "mensagem": mensagem_fixa})}\n\n'
                return

            # Requisição DIRETA e SIMPLES - sem treinamento, sem contexto prévio
            # SEM exibir etapas na interface
            prompt_direto = f"""Você é um analista de QA. A partir da seguinte estória do usuário, gere casos de teste:

"{conteudo_limpo}"

Responda ESTRITAMENTE com o JSON abaixo, sem textos explicativos:
{{
    "variaveis_identificadas": ["lista de variáveis"],
    "casos_de_teste": [
        {{
            "id": "CT01",
            "descricao": "Descrição do caso de teste",
            "classe_equivalencia": "Classe de equivalência",
            "dados_entrada": "Dados para testar",
            "resultado_esperado": "Resultado esperado",
            "tipo": "Positivo ou Negativo"
        }}
    ],
    "erro_validacao": ""
}}
"""

            try:
                resposta = await call_llm_with_retry(prompt_direto, max_retries=3, inicial_delay=2)
                
                if resposta is None:
                    yield f'data: {json.dumps({"tipo": "erro", "mensagem": "Falha na API após múltiplas tentativas"})}\n\n'
                    return
                
                texto_resposta = resposta.text.replace("```json", "").replace("```", "").strip()
                
                try:
                    dados_saida = json.loads(texto_resposta)
                    
                    if "variaveis_identificadas" not in dados_saida: 
                        dados_saida["variaveis_identificadas"] = []
                    if "casos_de_teste" not in dados_saida: 
                        dados_saida["casos_de_teste"] = []
                    
                    # Envia direto o resultado (SEM exibir etapas)
                    yield f'data: {json.dumps({"tipo": "completo", "dados": dados_saida, "modo": "sem_chaining"})}\n\n'
                    
                except json.JSONDecodeError as je:
                    print(f"[JSON ERROR] Erro ao fazer parse da resposta: {je}")
                    print(f"[JSON ERROR] Resposta recebida: {texto_resposta[:500]}")
                    yield f'data: {json.dumps({"tipo": "erro_processamento", "mensagem": "Erro na síntese dos dados - JSON inválido"})}\n\n'
            
            except Exception as api_error:
                print(f"[API ERROR] Erro na chamada à API: {api_error}")
                yield f'data: {json.dumps({"tipo": "erro", "mensagem": f"Erro na API: {str(api_error)[:200]}"})}\n\n'

        except Exception as e:
            print(f"[STREAM ERROR] Erro geral no stream (sem prompt chaining): {e}")
            yield f'data: {json.dumps({"tipo": "erro", "mensagem": f"Erro no servidor: {str(e)[:200]}"})}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def _gerar_tests_com_prompt_chaining(request: EstoriaRequest):
    """
    Abordagem COM prompt chaining: 4 etapas cognitivas separadas.
    """
    async def event_generator():
        try:
            # Carrega o arquivo de treinamento
            try:
                diretorio_atual = os.path.dirname(os.path.abspath(__file__))
                caminho_arquivo = os.path.join(diretorio_atual, "instrucoes_qa.txt")
                
                with open(caminho_arquivo, "r", encoding="utf-8") as f:
                    treinamento_qa = f.read()
            except FileNotFoundError:
                yield f'data: {json.dumps({"tipo": "erro", "mensagem": f"Arquivo instrucoes_qa.txt não encontrado"})}\n\n'
                return

            conteudo_limpo = request.estoria.strip()
            
            # Validação de tamanho mínimo
            if len(conteudo_limpo) < 100:
                mensagem_fixa = """A entrada está muito curta. Por favor, forneça uma estória estruturada.

Template esperado:

**Título:** [Descreva a funcionalidade de forma concisa]
**Como um** [tipo de usuário],
**Eu quero** [objetivo],
**Para que** [benefício].
**Detalhamento:** [Informações adicionais]
**Critérios de Aceitação:**
- Regra 1: [Com limite numérico ou tamanho mensurável]
- Regra 2: [Com limite numérico ou tamanho mensurável]
..."""
                
                yield f'data: {json.dumps({"tipo": "validacao_tamanho", "status": "falha", "mensagem": mensagem_fixa})}\n\n'
                return

            # ETAPA 1: VALIDAÇÃO DA ESTRUTURA DA ESTÓRIA
            yield f'data: {json.dumps({"tipo": "etapa_inicio", "etapa": 1, "titulo": "Validação da Estrutura da Estória", "descricao": "Verificando se a estória contém todos os componentes obrigatórios (Título, Stakeholder, Problema, Benefício, Detalhamento, Critérios Testáveis)...", "percentual": 0})}\n\n'

            prompt_etapa1 = f"""
        {treinamento_qa}

        === TAREFA ATUAL ===
        Analise a seguinte entrada fornecida pelo usuário:
        "{conteudo_limpo}"

        1. VERIFICAÇÃO DA ESTRUTURA E LITERAL:
           Você está PROIBIDO de deduzir a estrutura pelo contexto. Você deve agir como um analisador sintático cego. 
           Verifique se o texto contém as seguintes DECLARAÇÕES EXPLÍCITAS:
           - "titulo": Possui um título ou nome para a funcionalidade?
           - "stakeholder": O texto contém a sintaxe exata declarando o papel logo no início? (Ex: "Como um [papel]", "Sendo um [papel]"). Se não for localizado no texto o trecho "Como um" informando claramente qual tipo de usuário, você DEVE marcar "ausente" SEMPRE. NÃO DEVE deduzir o stakeholder baseando-se no título ou em palavras separadas no resto do texto.
           - "problema": O texto declara a ação que o ator deseja realizar? (ex: "desejo cadastrar", "quero acessar").
           - "beneficio": O texto declara o porquê ou valor de negócio final? (ex: "para poder...", "com o objetivo de...").
           - "detalhamento": Possui contexto adicional ou regras descritivas?
           - "criterios_aceitacao": Possui critérios de aceitação CLAROS e TESTÁVEIS? (numéricos ou descritivos)
           - "criterios_aceitacao_mensuraveis": Possui regras com limites numéricos, intervalos ou tamanhos verificáveis? (pode estar ausente mesmo que a estória seja válida)

        2. REGRA DE STATUS:
           A estória é "valido" SE tiver: titulo, stakeholder, problema, beneficio, detalhamento E criterios_aceitacao (não pode ser vago/subjetivo).
           A estória é "invalido" SE: faltarem items estruturais OR os critérios de aceitação forem muito subjetivos/intestáveis.
           O campo "criterios_aceitacao_mensuraveis" é informativo (pode estar ausente mesmo que a estória seja válida).

        3. DETERMINAÇÃO DA TÉCNICA:
           - Se "criterios_aceitacao_mensuraveis" = "presente": usar "tecnica_aplicada": "Particionamento de Equivalência + Análise de Valor Limite"
           - Se "criterios_aceitacao_mensuraveis" = "ausente" mas "criterios_aceitacao" = "presente": usar "tecnica_aplicada": "Testes Descritivos Baseados em Critérios (sem análise de valor limite)"

        Responda APENAS com um JSON puro neste formato:
        {{
            "auditoria_checklist": {{
                "titulo": "presente" ou "ausente",
                "stakeholder": "presente" ou "ausente",
                "problema": "presente" ou "ausente",
                "beneficio": "presente" ou "ausente",
                "detalhamento": "presente" ou "ausente",
                "criterios_aceitacao": "presente" ou "ausente",
                "criterios_aceitacao_mensuraveis": "presente" ou "ausente"
            }},
            "status": "valido" ou "invalido",
            "mensagem_erro": "Se invalido, descreva brevemente o motivo.",
            "variaveis_identificadas": ["lista das variáveis numéricas/tamanhos encontrados, vazio se não houver"],
            "tecnica_aplicada": "Particionamento de Equivalência + Análise de Valor Limite" ou "Testes Descritivos Baseados em Critérios (sem análise de valor limite)" ou "Nenhuma",
            "analise_classes": "Detalhe da análise de classes e técnicas aplicadas, baseado nos exemplos."
        }}
        """

            try:
                resposta_etapa1 = await call_llm_with_retry(prompt_etapa1, max_retries=3, inicial_delay=2)
                
                if resposta_etapa1 is None:
                    yield f'data: {json.dumps({"tipo": "erro", "mensagem": "Falha na Etapa 1 (Validação) após múltiplas tentativas"})}\n\n'
                    return
                
                texto_etapa1 = resposta_etapa1.text.replace("```json", "").replace("```", "").strip()
                
                dados_analise = json.loads(texto_etapa1)
                
                # Envia resultado da Etapa 1
                checklist_resumo = {k: v for k, v in dados_analise.get("auditoria_checklist", {}).items()}
                yield f'data: {json.dumps({"tipo": "etapa_resultado", "etapa": 1, "percentual": 25, "checklist": checklist_resumo, "status": dados_analise.get("status", "invalido"), "tecnica_aplicada": dados_analise.get("tecnica_aplicada", "Nenhuma")})}\n\n'
                
                # Atraso de 2 segundos para percepção visual de progresso
                await asyncio.sleep(2)
                
                # Verificação de status (APENAS se invalido)
                if dados_analise.get("status") == "invalido":
                    checklist = dados_analise.get("auditoria_checklist", {})
                    
                    mapa_nomes = {
                        "titulo": "'Título'",
                        "stakeholder": "'Stakeholder (Como um...)'",
                        "problema": "'Problema (Eu quero...)'",
                        "beneficio": "'Benefício (Para...)'",
                        "detalhamento": "'Detalhamento'",
                        "criterios_aceitacao": "'Critérios de Aceitação'",
                        "criterios_aceitacao_mensuraveis": "'Critérios de Aceitação (com limites mensuráveis)'"
                    }
                    
                    itens_ausentes = [mapa_nomes.get(k, k) for k, v in checklist.items() if v == "ausente"]
                    texto_ausentes = ", ".join(itens_ausentes) if itens_ausentes else "Itens obrigatórios não detectados"
                    
                    mensagem_ia = dados_analise.get("mensagem_erro", "")
                    mensagem_erro = f"""A estória está incompleta ou possui critérios não testáveis.

Motivo: {mensagem_ia}
Itens faltando/inválidos: {texto_ausentes}.

Template esperado:

**Título:** [Descreva a funcionalidade de forma concisa]
**Como um** [tipo de usuário],
**Eu quero** [objetivo],
**Para que** [benefício].
**Detalhamento:** [Informações adicionais]
**Critérios de Aceitação:**
- Regra 1: [Critério testável, com ou sem limite numérico]
- Regra 2: [Critério testável, com ou sem limite numérico]
..."""
                    
                    yield f'data: {json.dumps({"tipo": "validacao_falhou", "mensagem": mensagem_erro, "tecnica_aplicada": "Nenhuma"})}\n\n'
                    return
                    
            except json.JSONDecodeError:
                dados_analise = {"variaveis_identificadas": [], "analise_classes": texto_etapa1}

            # ETAPA 2: ANÁLISE ADAPTATIVA (baseada na técnica aplicada)
            yield f'data: {json.dumps({"tipo": "etapa_inicio", "etapa": 2, "titulo": "Análise", "descricao": f"Analisando a estória conforme a técnica: {dados_analise.get('tecnica_aplicada', 'Nenhuma')}...", "percentual": 25})}\n\n'

            # Verifica qual técnica foi aplicada
            tecnica_aplicada = dados_analise.get("tecnica_aplicada", "Nenhuma")
            
            if tecnica_aplicada == "Particionamento de Equivalência + Análise de Valor Limite":
                # Faz análise de PE e AVL
                prompt_etapa2 = f"""
        Você é um especialista em Engenharia de Testes com domínio em Particionamento de Equivalência e Análise de Valor Limite.
        
        Estória Original: "{conteudo_limpo}"
        
        Análise Prévia Estrutural: {json.dumps(dados_analise.get("auditoria_checklist", {}))}

        TAREFA: Com base na estória, identifique:
        
        1. CLASSES DE EQUIVALÊNCIA (PE):
           - Quais são as classes válidas?
           - Quais são as classes inválidas?
           - Liste cada classe com exemplos concretos
           
        2. ANÁLISE DE VALOR LIMITE (AVL):
           - Qual é o valor mínimo válido?
           - Qual é o valor máximo válido?
           - Qual é o valor mínimo-1 (abaixo do válido)?
           - Qual é o valor máximo+1 (acima do válido)?
           
        3. REGRAS IDENTIFICADAS:
           - Lista todas as regras de negócio/restrições mencionadas na estória
           - Para cada regra, indique: tipo, descrição, limite (se numérico)

        Responda APENAS com JSON puro neste formato:
        {{
            "classes_equivalencia": {{
                "validas": [
                    {{
                        "nome": "Classe Válida 1",
                        "descricao": "Descrição",
                        "exemplos": ["exemplo1", "exemplo2"]
                    }}
                ],
                "invalidas": [
                    {{
                        "nome": "Classe Inválida 1",
                        "descricao": "Descrição",
                        "exemplos": ["exemplo1", "exemplo2"]
                    }}
                ]
            }},
            "valores_limites": [
                {{
                    "variavel": "Nome da variável",
                    "minimo_valido": "valor",
                    "minimo_invalido": "valor",
                    "maximo_valido": "valor",
                    "maximo_invalido": "valor"
                }}
            ],
            "regras_identificadas": [
                {{
                    "numero": 1,
                    "descricao": "Descrição da regra",
                    "tipo": "Obrigatória/Restrição/Validação",
                    "limite": "Se aplicável"
                }}
            ]
        }}
        """
            else:
                # Faz análise de critérios descritivos (SEM PE e AVL)
                prompt_etapa2 = f"""
        Você é um Analista de QA especialista em testes descritivos.
        
        Estória Original: "{conteudo_limpo}"
        
        TAREFA: Com base na estória, identifique:
        
        1. CRITÉRIOS TESTÁVEIS (descritivos):
           - Quais são os critérios de aceitação mencionados?
           - Para cada critério, identifique cenários POSITIVOS (que atendem) e NEGATIVOS (que violam)
           - Liste cada cenário com descrição clara
           
        2. VARIÁVEIS ENVOLVIDAS:
           - Quais são as variáveis/campos mencionados?
           - Quais são os tipos (texto, seleção, etc)?
           - Quais são as restrições (caracteres permitidos, obrigatoriedade, etc)?
           
        3. REGRAS IDENTIFICADAS:
           - Lista todas as regras de negócio/restrições mencionadas na estória
           - Para cada regra, indique: tipo, descrição

        Responda APENAS com JSON puro neste formato:
        {{
            "criterios_descritivos": [
                {{
                    "numero": 1,
                    "criterio": "Descrição do critério",
                    "cenarios_positivos": ["Cenário 1 que atende o critério", "Cenário 2 que atende o critério"],
                    "cenarios_negativos": ["Cenário 1 que viola o critério", "Cenário 2 que viola o critério"]
                }}
            ],
            "variaveis": [
                {{
                    "nome": "Nome da variável",
                    "tipo": "Tipo (texto, número, seleção, etc)",
                    "restricoes": "Restrições mencionadas"
                }}
            ],
            "regras_identificadas": [
                {{
                    "numero": 1,
                    "descricao": "Descrição da regra",
                    "tipo": "Obrigatória/Restrição/Validação"
                }}
            ]
        }}
        """

            # Executa a análise de etapa 2
            try:
                resposta_etapa2 = await call_llm_with_retry(prompt_etapa2, max_retries=3, inicial_delay=2)
                
                if resposta_etapa2 is None:
                    yield f'data: {json.dumps({"tipo": "erro", "mensagem": "Falha na Etapa 2 (Análise) após múltiplas tentativas"})}\n\n'
                    return
                
                texto_etapa2 = resposta_etapa2.text.replace("```json", "").replace("```", "").strip()
                
                analise_etapa2 = json.loads(texto_etapa2)
            except json.JSONDecodeError:
                if tecnica_aplicada == "Particionamento de Equivalência + Análise de Valor Limite":
                    analise_etapa2 = {
                        "classes_equivalencia": {"validas": [], "invalidas": []},
                        "valores_limites": [],
                        "regras_identificadas": []
                    }
                else:
                    analise_etapa2 = {
                        "criterios_descritivos": [],
                        "variaveis": [],
                        "regras_identificadas": []
                    }
            except Exception as e:
                print(f"[ETAPA2 ERROR] Erro na Etapa 2: {e}")
                yield f'data: {json.dumps({"tipo": "erro", "mensagem": f"Erro na Etapa 2: {str(e)[:200]}"})}\n\n'
                return

            # Envia resultado da Etapa 2
            if tecnica_aplicada == "Particionamento de Equivalência + Análise de Valor Limite":
                qtd_classes_validas = len(analise_etapa2.get("classes_equivalencia", {}).get("validas", []))
                qtd_classes_invalidas = len(analise_etapa2.get("classes_equivalencia", {}).get("invalidas", []))
                qtd_regras = len(analise_etapa2.get("regras_identificadas", []))
                yield f'data: {json.dumps({"tipo": "etapa_resultado", "etapa": 2, "percentual": 50, "classes_validas": qtd_classes_validas, "classes_invalidas": qtd_classes_invalidas, "regras": qtd_regras})}\n\n'
            else:
                qtd_criterios = len(analise_etapa2.get("criterios_descritivos", []))
                qtd_variaveis = len(analise_etapa2.get("variaveis", []))
                qtd_regras = len(analise_etapa2.get("regras_identificadas", []))
                yield f'data: {json.dumps({"tipo": "etapa_resultado", "etapa": 2, "percentual": 50, "criterios": qtd_criterios, "variaveis": qtd_variaveis, "regras": qtd_regras})}\n\n'
            
            # Atraso de 2 segundos para percepção visual de progresso
            await asyncio.sleep(2)

            # ETAPA 3: GERAÇÃO DE CASOS DE TESTE
            yield f'data: {json.dumps({"tipo": "etapa_inicio", "etapa": 3, "titulo": "Geração de Casos de Teste (Cenários)", "descricao": "Sintetizando os casos de teste conforme a técnica aplicada...", "percentual": 75})}\n\n'

            # Preparar prompt da etapa 3 baseado na técnica
            if tecnica_aplicada == "Particionamento de Equivalência + Análise de Valor Limite":
                prompt_etapa3 = f"""
        Atue como Analista de QA especialista em Engenharia de Testes.
        
        Estória Original: "{conteudo_limpo}"
        
        Classes de Equivalência Identificadas: {json.dumps(analise_etapa2.get("classes_equivalencia", {}))}
        
        Valores Limites: {json.dumps(analise_etapa2.get("valores_limites", []))}
        
        Regras de Negócio: {json.dumps(analise_etapa2.get("regras_identificadas", []))}

        Com base estritamente nas classes de equivalência e valores limites acima, gere os Casos de Teste (Cenários).
        
        INSTRUÇÕES:
        - Crie UM caso de teste para CADA classe de equivalência
        - Para valores numéricos, crie casos para: Mínimo Válido, Mínimo-1 (inválido), Máximo Válido, Máximo+1 (inválido)
        - Para cada caso, determine se é POSITIVO (deve passar) ou NEGATIVO (deve falhar)
        - A descrição deve ser clara e testável
        
        Responda ESTRITAMENTE com o JSON no formato abaixo, sem textos explicativos:
        {{
            "variaveis_identificadas": {json.dumps(dados_analise.get("variaveis_identificadas", []))},
            "tecnica_aplicada": "Particionamento de Equivalência + Análise de Valor Limite",
            "casos_de_teste": [
                {{
                    "id": "CT01",
                    "descricao": "string explicativa clara e testável",
                    "classe_equivalencia": "Ex: Classe Válida - Valores dentro do intervalo",
                    "dados_entrada": "Valor concreto a ser testado",
                    "resultado_esperado": "Comportamento esperado do sistema",
                    "tipo": "Positivo ou Negativo"
                }}
            ],
            "erro_validacao": ""
        }}
        """
            else:
                prompt_etapa3 = f"""
        Atue como Analista de QA especialista em testes descritivos.
        
        Estória Original: "{conteudo_limpo}"
        
        Critérios Testáveis Identificados: {json.dumps(analise_etapa2.get("criterios_descritivos", []))}
        
        Variáveis: {json.dumps(analise_etapa2.get("variaveis", []))}
        
        Regras de Negócio: {json.dumps(analise_etapa2.get("regras_identificadas", []))}

        Com base estritamente nos critérios e variáveis acima, gere os Casos de Teste.
        
        INSTRUÇÕES:
        - Para cada critério testável, crie casos de teste para: POSITIVOS (que atendem o critério) e NEGATIVOS (que violam o critério)
        - Cada caso deve descrever claramente a ação e o resultado esperado
        - NÃO aplique análise de valor limite (critérios são descritivos, não numéricos)
        - Baseie-se nas restrições mencionadas nos critérios
        
        Responda ESTRITAMENTE com o JSON no formato abaixo, sem textos explicativos:
        {{
            "variaveis_identificadas": {json.dumps(dados_analise.get("variaveis_identificadas", []))},
            "tecnica_aplicada": "Testes Descritivos Baseados em Critérios (sem análise de valor limite)",
            "casos_de_teste": [
                {{
                    "id": "CT01",
                    "descricao": "string explicativa clara e testável",
                    "classe_equivalencia": "Ex: Cenário Positivo - Atende o critério de aceitação",
                    "dados_entrada": "Descrição ou valor a ser testado",
                    "resultado_esperado": "Comportamento esperado do sistema",
                    "tipo": "Positivo ou Negativo"
                }}
            ],
            "erro_validacao": ""
        }}
        """

            try:
                resposta_etapa3 = await call_llm_with_retry(prompt_etapa3, max_retries=3, inicial_delay=2)
                
                if resposta_etapa3 is None:
                    yield f'data: {json.dumps({"tipo": "erro", "mensagem": "Falha na Etapa 3 (Geração de Testes) após múltiplas tentativas"})}\n\n'
                    return
                
                texto_etapa3 = resposta_etapa3.text.replace("```json", "").replace("```", "").strip()
                
                dados_saida = json.loads(texto_etapa3)
                
                if "variaveis_identificadas" not in dados_saida: 
                    dados_saida["variaveis_identificadas"] = dados_analise.get("variaveis_identificadas", [])
                if "casos_de_teste" not in dados_saida: 
                    dados_saida["casos_de_teste"] = []
                if "tecnica_aplicada" not in dados_saida:
                    dados_saida["tecnica_aplicada"] = tecnica_aplicada
                
                # Envia resultado da Etapa 3
                yield f'data: {json.dumps({"tipo": "etapa_resultado", "etapa": 3, "percentual": 100, "quantidade_testes": len(dados_saida.get("casos_de_teste", []))})}\n\n'
                
                # Atraso de 2 segundos para percepção visual de progresso
                await asyncio.sleep(2)
                
                # Envia os dados finais
                yield f'data: {json.dumps({"tipo": "completo", "dados": dados_saida, "analise_classes": analise_etapa2, "modo": "com_chaining"})}\n\n'

            except json.JSONDecodeError as je:
                print(f"[JSON ERROR] Erro ao fazer parse da Etapa 3: {je}")
                yield f'data: {json.dumps({"tipo": "erro_processamento", "mensagem": "Erro na síntese dos casos de teste - JSON inválido"})}\n\n'
            except Exception as e3:
                print(f"[ETAPA3 ERROR] Erro na Etapa 3: {e3}")
                yield f'data: {json.dumps({"tipo": "erro", "mensagem": f"Erro na Etapa 3: {str(e3)[:200]}"})}\n\n'

        except Exception as e:
            print(f"[STREAM ERROR] Erro geral no stream (com chaining): {e}")
            yield f'data: {json.dumps({"tipo": "erro", "mensagem": f"Erro no servidor: {str(e)[:200]}"})}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")