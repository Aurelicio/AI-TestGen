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
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
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
                if tentativa < max_retries - 1:
                    delay = inicial_delay * (2 ** tentativa)
                    print(f"[LLM RETRY] Aguardando {delay}s antes de tentar novamente...")
                    await asyncio.sleep(delay)
                    
        except Exception as e:
            erro_str = str(e)
            print(f"[LLM ERROR] Tentativa {tentativa + 1} falhou com erro: {erro_str}")
            
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
           - "criterios_aceitacao_mensuraveis": Possui regras claras contendo limites numéricos, intervalos ou tamanhos verificáveis?

        2. REGRA DE STATUS:
           Se QUALQUER item do checklist acima for marcado como "ausente", o "status" DEVE obrigatoriamente ser "invalido".

        Responda APENAS com um JSON puro neste formato:
        {{
            "auditoria_checklist": {{
                "titulo": "presente" ou "ausente",
                "stakeholder": "presente" ou "ausente",
                "problema": "presente" ou "ausente",
                "beneficio": "presente" ou "ausente",
                "detalhamento": "presente" ou "ausente",
                "criterios_aceitacao_mensuraveis": "presente" ou "ausente"
            }},
            "status": "valido" ou "invalido",
            "mensagem_erro": "Se invalido, preencha com 'Falha estrutural'.",
            "variaveis_identificadas": ["lista das variáveis numéricas/tamanhos encontrados"],
            "analise_classes": "Detalhe do PE e AVL baseado nos exemplos, apenas se válido."
        }}
        """

        resposta_etapa1 = client.models.generate_content(
            model=modelo_llm,
            contents=prompt_etapa1
        )
        
        texto_etapa1 = resposta_etapa1.text.replace("```json", "").replace("```", "").strip()
        
        try:
            dados_analise = json.loads(texto_etapa1)
            
            # Montagem da mensagem de erro
            if dados_analise.get("status") == "invalido":
                checklist = dados_analise.get("auditoria_checklist", {})
                
                # Mapeamento para nomes na interface
                mapa_nomes = {
                    "titulo": "'Título'",
                    "stakeholder": "'Stakeholder (Como um...)'",
                    "problema": "'Problema (Eu quero...)'",
                    "beneficio": "'Benefício (Para...)'",
                    "detalhamento": "'Detalhamento'",
                    "criterios_aceitacao_mensuraveis": "'Critérios de Aceitação (com limites mensuráveis)'"
                }
                
                # Coleta dos itens que a IA marcou como "ausente"
                itens_ausentes = [mapa_nomes.get(k, k) for k, v in checklist.items() if v == "ausente"]
                texto_ausentes = ", ".join(itens_ausentes) if itens_ausentes else "Itens obrigatórios não detectados"
                
                # Template fixo concatenado com as falhas
                mensagem_fixa = f"""A estória está incompleta. É obrigatório o preenchimento/correção dos seguintes itens: {texto_ausentes}.

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
                
        except json.JSONDecodeError:
            dados_analise = {"variaveis_identificadas": [], "analise_classes": texto_etapa1}

        # ETAPA 2: Montagem dos Casos de Teste

        prompt_etapa2 = f"""
        Atue como Analista de QA.
        
        Estória Original: "{conteudo_limpo}"
        Análise Prévia de Classes (PE e AVL): {json.dumps(dados_analise.get("analise_classes", ""))}

        Com base estritamente na Análise Prévia, gere os Casos de Teste. 
        Você DEVE criar Casos de Teste englobando os valores limites (Limite exato, Limite-1, Limite+1) e classes válidas/inválidas que foram documentadas na análise prévia.

        Responda ESTRITAMENTE com o JSON no formato abaixo, sem textos explicativos:
        {{
            "variaveis_identificadas": {json.dumps(dados_analise.get("variaveis_identificadas", []))},
            "casos_de_teste": [
                {{
                    "id": "CT01",
                    "descricao": "string explicativa",
                    "classe_equivalencia": "Ex: Valor Limite Inferior Válido",
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
                
            return dados_saida

        except json.JSONDecodeError:
            return {
                "variaveis_identificadas": [],
                "casos_de_teste": [],
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
    Apenas: estória → geração de casos de teste no formato esperado.
    
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
            yield f'data: {json.dumps({"tipo": "etapa_inicio", "etapa": 1, "titulo": "Validação da Estrutura da Estória", "descricao": "Verificando se a estória contém todos os componentes obrigatórios (Título, Stakeholder, Problema, Benefício, Detalhamento, Critérios Mensuráveis)...", "percentual": 0})}\n\n'

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
           - "criterios_aceitacao_mensuraveis": Possui regras claras contendo limites numéricos, intervalos ou tamanhos verificáveis?

        2. REGRA DE STATUS:
           Se QUALQUER item do checklist acima for marcado como "ausente", o "status" DEVE obrigatoriamente ser "invalido".

        Responda APENAS com um JSON puro neste formato:
        {{
            "auditoria_checklist": {{
                "titulo": "presente" ou "ausente",
                "stakeholder": "presente" ou "ausente",
                "problema": "presente" ou "ausente",
                "beneficio": "presente" ou "ausente",
                "detalhamento": "presente" ou "ausente",
                "criterios_aceitacao_mensuraveis": "presente" ou "ausente"
            }},
            "status": "valido" ou "invalido",
            "mensagem_erro": "Se invalido, preencha com 'Falha estrutural'.",
            "variaveis_identificadas": ["lista das variáveis numéricas/tamanhos encontrados"],
            "analise_classes": "Detalhe do PE e AVL baseado nos exemplos, apenas se válido."
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
                yield f'data: {json.dumps({"tipo": "etapa_resultado", "etapa": 1, "percentual": 25, "checklist": checklist_resumo, "status": dados_analise.get("status", "invalido")})}\n\n'
                
                # Atraso de 2 segundos para percepção visual de progresso
                await asyncio.sleep(2)
                
                # Verificação de status
                if dados_analise.get("status") == "invalido":
                    checklist = dados_analise.get("auditoria_checklist", {})
                    
                    mapa_nomes = {
                        "titulo": "'Título'",
                        "stakeholder": "'Stakeholder (Como um...)'",
                        "problema": "'Problema (Eu quero...)'",
                        "beneficio": "'Benefício (Para...)'",
                        "detalhamento": "'Detalhamento'",
                        "criterios_aceitacao_mensuraveis": "'Critérios de Aceitação (com limites mensuráveis)'"
                    }
                    
                    itens_ausentes = [mapa_nomes.get(k, k) for k, v in checklist.items() if v == "ausente"]
                    texto_ausentes = ", ".join(itens_ausentes) if itens_ausentes else "Itens obrigatórios não detectados"
                    
                    mensagem_erro = f"""A estória está incompleta. É obrigatório o preenchimento/correção dos seguintes itens: {texto_ausentes}.

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
                    
                    yield f'data: {json.dumps({"tipo": "validacao_falhou", "mensagem": mensagem_erro})}\n\n'
                    return
                    
            except json.JSONDecodeError:
                dados_analise = {"variaveis_identificadas": [], "analise_classes": texto_etapa1}

            # ETAPA 2: APLICAÇÃO DA TÉCNICA FEW SHOT
            yield f'data: {json.dumps({"tipo": "etapa_inicio", "etapa": 2, "titulo": "Aplicação da Técnica Few Shot", "descricao": "Treinando o modelo com exemplos de Particionamento de Equivalência (PE) e Análise de Valor Limite (AVL) para compreender as regras da estória...", "percentual": 25})}\n\n'

            # O Few Shot é feito através do arquivo de treinamento que já foi carregado
            # Aqui apenas é confirmado que o modelo recebeu o treinamento
            yield f'data: {json.dumps({"tipo": "etapa_resultado", "etapa": 2, "percentual": 50, "tecnicas_aplicadas": ["Few Shot Learning", "In-Context Learning", "Constraint-Based Reasoning"]})}\n\n'
            
            # Atraso de 2 segundos para percepção visual de progresso
            await asyncio.sleep(2)

            # ETAPA 3: IDENTIFICAÇÃO DE CLASSES E REGRAS
            yield f'data: {json.dumps({"tipo": "etapa_inicio", "etapa": 3, "titulo": "Identificação de Classes de Equivalência e Regras", "descricao": "Analisando a estória para identificar as classes de equivalência válidas, inválidas e os valores limites conforme as técnicas de PE e AVL...", "percentual": 50})}\n\n'

            prompt_etapa3 = f"""
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

            try:
                resposta_etapa3 = await call_llm_with_retry(prompt_etapa3, max_retries=3, inicial_delay=2)
                
                if resposta_etapa3 is None:
                    yield f'data: {json.dumps({"tipo": "erro", "mensagem": "Falha na Etapa 3 (Classes e Limites) após múltiplas tentativas"})}\n\n'
                    return
                
                texto_etapa3 = resposta_etapa3.text.replace("```json", "").replace("```", "").strip()
                
                analise_classes = json.loads(texto_etapa3)
            except json.JSONDecodeError:
                analise_classes = {
                    "classes_equivalencia": {"validas": [], "invalidas": []},
                    "valores_limites": [],
                    "regras_identificadas": []
                }
            except Exception as e:
                print(f"[ETAPA3 ERROR] Erro na Etapa 3: {e}")
                yield f'data: {json.dumps({"tipo": "erro", "mensagem": f"Erro na Etapa 3: {str(e)[:200]}"})}\n\n'
                return

            # Conta regras e classes identificadas
            qtd_classes_validas = len(analise_classes.get("classes_equivalencia", {}).get("validas", []))
            qtd_classes_invalidas = len(analise_classes.get("classes_equivalencia", {}).get("invalidas", []))
            qtd_regras = len(analise_classes.get("regras_identificadas", []))
            
            yield f'data: {json.dumps({"tipo": "etapa_resultado", "etapa": 3, "percentual": 75, "classes_validas": qtd_classes_validas, "classes_invalidas": qtd_classes_invalidas, "regras": qtd_regras})}\n\n'
            
            # Atraso de 2 segundos para percepção visual de progresso
            await asyncio.sleep(2)

            # ETAPA 4: GERAÇÃO DE CASOS DE TESTE
            yield f'data: {json.dumps({"tipo": "etapa_inicio", "etapa": 4, "titulo": "Geração de Casos de Teste (Cenários)", "descricao": "Sintetizando os casos de teste combinando as classes de equivalência e valores limites identificados na etapa anterior...", "percentual": 75})}\n\n'

            prompt_etapa4 = f"""
        Atue como Analista de QA especialista em Engenharia de Testes.
        
        Estória Original: "{conteudo_limpo}"
        
        Classes de Equivalência Identificadas: {json.dumps(analise_classes.get("classes_equivalencia", {}))}
        
        Valores Limites: {json.dumps(analise_classes.get("valores_limites", []))}
        
        Regras de Negócio: {json.dumps(analise_classes.get("regras_identificadas", []))}

        Com base estritamente nas classes de equivalência e valores limites acima, gere os Casos de Teste (Cenários).
        
        INSTRUÇÕES:
        - Crie UM caso de teste para CADA classe de equivalência
        - Para valores numéricos, crie casos para: Mínimo Válido, Mínimo-1 (inválido), Máximo Válido, Máximo+1 (inválido)
        - Para cada caso, determine se é POSITIVO (deve passar) ou NEGATIVO (deve falhar)
        - A descrição deve ser clara e testável
        
        Responda ESTRITAMENTE com o JSON no formato abaixo, sem textos explicativos:
        {{
            "variaveis_identificadas": {json.dumps(dados_analise.get("variaveis_identificadas", []))},
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

            try:
                resposta_etapa4 = await call_llm_with_retry(prompt_etapa4, max_retries=3, inicial_delay=2)
                
                if resposta_etapa4 is None:
                    yield f'data: {json.dumps({"tipo": "erro", "mensagem": "Falha na Etapa 4 (Geração de Testes) após múltiplas tentativas"})}\n\n'
                    return
                
                texto_etapa4 = resposta_etapa4.text.replace("```json", "").replace("```", "").strip()
                
                dados_saida = json.loads(texto_etapa4)
                
                if "variaveis_identificadas" not in dados_saida: 
                    dados_saida["variaveis_identificadas"] = dados_analise.get("variaveis_identificadas", [])
                if "casos_de_teste" not in dados_saida: 
                    dados_saida["casos_de_teste"] = []
                
                # Envia resultado da Etapa 4
                yield f'data: {json.dumps({"tipo": "etapa_resultado", "etapa": 4, "percentual": 100, "quantidade_testes": len(dados_saida.get("casos_de_teste", []))})}\n\n'
                
                # Atraso de 2 segundos para percepção visual de progresso
                await asyncio.sleep(2)
                
                # Envia os dados finais
                yield f'data: {json.dumps({"tipo": "completo", "dados": dados_saida, "analise_classes": analise_classes, "modo": "com_chaining"})}\n\n'

            except json.JSONDecodeError as je:
                print(f"[JSON ERROR] Erro ao fazer parse da Etapa 4: {je}")
                yield f'data: {json.dumps({"tipo": "erro_processamento", "mensagem": "Erro na síntese dos casos de teste - JSON inválido"})}\n\n'
            except Exception as e4:
                print(f"[ETAPA4 ERROR] Erro na Etapa 4: {e4}")
                yield f'data: {json.dumps({"tipo": "erro", "mensagem": f"Erro na Etapa 4: {str(e4)[:200]}"})}\n\n'

        except Exception as e:
            print(f"[STREAM ERROR] Erro geral no stream (com chaining): {e}")
            yield f'data: {json.dumps({"tipo": "erro", "mensagem": f"Erro no servidor: {str(e)[:200]}"})}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")