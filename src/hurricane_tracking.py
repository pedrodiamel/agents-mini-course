import requests
from typing import TypedDict, List, Dict, Optional, Union
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from datetime import datetime
import openai
import os
import logging

# --- Configuração ---
from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv()) # read local .env file
openai.api_key = os.environ['OPENAI_API_KEY']

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constantes ---
NOAA_API_URL = "https://www.nhc.noaa.gov/CurrentStorms.json"
REQUEST_TIMEOUT = 10  # seconds

STORM_CLASSIFICATIONS = {
    "HU": "Furacão",
    "TS": "Tempestade Tropical",
    "TD": "Depressão Tropical",
    "SD": "Distúrbio Tropical",
    "PTC": "Ciclone Pós-Tropical",
    "STD": "Depressão Subtropical"
}

# --- Estado do grafo ---
class HurricaneState(TypedDict):
    question: str
    storms_data: List[Dict]
    synthesis: str
    error: Optional[str]

# --- Tool: NOAA Hurricane Data ---
def get_storm_classification(code: str) -> str:
    """Retorna descrição legível da classificação do furacão"""
    return STORM_CLASSIFICATIONS.get(code, "Outro Sistema")


def get_active_storms() -> List[Dict]:
    """
    Busca dados de tempestades ativas na API da NOAA com tratamento de erros robusto

    Returns:
        List[Dict]: Lista de dicionários com dados das tempestades ou lista vazia em caso de erro
    """
    try:
        logger.info(f"Buscando dados da API NOAA: {NOAA_API_URL}")
        response = requests.get(NOAA_API_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        active_storms = []

        storms = data.get("activeStorms", [])
        if not storms:
            logger.info("Nenhuma tempestade ativa encontrada")
            return []

        for storm in storms:
            storm_info = {
                "id": storm.get("id", "N/A"),
                "nome": storm.get("name", "Sem nome"),
                "classificacao": {
                    "codigo": storm.get("classification", "N/A"),
                    "descricao": get_storm_classification(storm.get("classification"))
                },
                "intensidade_ventos_mph": storm.get("intensity", 0),
                "pressao_mb": storm.get("pressure", 0),
                "localizacao": {
                    "latitude": storm.get("latitudeNumeric", 0),
                    "longitude": storm.get("longitudeNumeric", 0),
                    "latitude_texto": storm.get("latitude", "N/A"),
                    "longitude_texto": storm.get("longitude", "N/A")
                },
                "movimento": {
                    "direcao_graus": storm.get("movementDir", 0),
                    "velocidade_nos": storm.get("movementSpeed", 0)
                },
                "ultima_atualizacao": storm.get("lastUpdate", "N/A"),
                "fontes": {
                    "aviso_publico": storm.get("publicAdvisory", {}).get("url"),
                    "grafico_previsao": storm.get("forecastGraphics", {}).get("url"),
                    "tracado_previsao": storm.get("forecastTrack", {}).get("kmzFile"),
                    "cone_previsao": storm.get("trackCone", {}).get("kmzFile"),
                    "discussao": storm.get("forecastDiscussion", {}).get("url")
                }
            }
            active_storms.append(storm_info)
            logger.info(f"Tempestade encontrada: {storm_info['nome']} ({storm_info['classificacao']['descricao']})")

        return active_storms

    except requests.exceptions.Timeout:
        logger.error(f"Timeout ao conectar com a API NOAA após {REQUEST_TIMEOUT}s")
        return []
    except requests.exceptions.ConnectionError:
        logger.error("Erro de conexão com a API NOAA")
        return []
    except requests.exceptions.HTTPError as e:
        logger.error(f"Erro HTTP da API NOAA: {e}")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao buscar dados da API NOAA: {e}")
        return []
    except (ValueError, KeyError) as e:
        logger.error(f"Erro ao processar resposta da API: {e}")
        return []
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        return []



# --- Etapa 1: Busca ---
def fetch_hurricane_data(state: HurricaneState) -> Dict:
    """Busca dados atualizados de furacões"""
    logger.info("🌀 Buscando dados de furacões ativos...")
    storms = get_active_storms()

    if not storms:
        return {
            "storms_data": [],
            "error": "Não foi possível obter dados da API NOAA ou não há tempestades ativas."
        }

    return {"storms_data": storms, "error": None}


def format_storm_context(storms: List[Dict]) -> str:
    """Formata dados das tempestades em texto legível"""
    context_parts = []

    for storm in storms:
        storm_text = f"""
🌀 {storm['nome']} ({storm['classificacao']['descricao']})
   • Intensidade: {storm['intensidade_ventos_mph']} mph
   • Pressão: {storm['pressao_mb']} mb
   • Localização: {storm['localizacao']['latitude_texto']}, {storm['localizacao']['longitude_texto']}
   • Movimento: {storm['movimento']['direcao_graus']}° a {storm['movimento']['velocidade_nos']} nós
   • Última atualização: {storm['ultima_atualizacao']}"""

        # Adiciona fontes disponíveis
        if storm['fontes'].get('aviso_publico'):
            storm_text += f"\n   • Aviso Público: {storm['fontes']['aviso_publico']}"
        if storm['fontes'].get('grafico_previsao'):
            storm_text += f"\n   • Gráfico: {storm['fontes']['grafico_previsao']}"

        context_parts.append(storm_text)

    return "\n".join(context_parts)


# --- Etapa 2: Síntese ---
def summarize_storms(state: HurricaneState) -> Dict:
    """Gera resumo inteligente baseado nos dados e na pergunta do usuário"""
    logger.info("🧠 Gerando resumo meteorológico...")

    # Se houve erro na busca
    if state.get("error"):
        return {"synthesis": f"⚠️ {state['error']}"}

    # Se não há tempestades
    if not state["storms_data"]:
        return {"synthesis": "✅ Nenhum sistema tropical ativo detectado no momento no Atlântico e Caribe."}

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)

    # Formata contexto de forma estruturada
    context = format_storm_context(state["storms_data"])

    # Usa a pergunta do usuário no prompt
    user_question = state.get("question", "Qual é o status atual dos furacões?")

    prompt = f"""Você é um meteorologista experiente especializado em sistemas tropicais.

Pergunta do usuário: {user_question}

Dados atuais da NOAA sobre sistemas tropicais ativos:
{context}

Gere um resumo técnico e claro que responda à pergunta do usuário, incluindo:
- Nome e classificação de cada sistema (ex: Furacão, Tempestade Tropical)
- Localização geográfica e coordenadas
- Direção, velocidade de movimento e intensidade
- Pressão atmosférica central
- Possíveis áreas em risco considerando a trajetória
- Recomendações de monitoramento

Use linguagem clara mas técnica. Organize as informações de forma estruturada."""

    try:
        result = llm.invoke(prompt)
        return {"synthesis": result.content}
    except Exception as e:
        logger.error(f"Erro ao gerar síntese: {e}")
        return {"synthesis": f"⚠️ Erro ao gerar resumo: {str(e)}\n\nDados brutos:\n{context}"}



# --- Construção do grafo ---
def create_hurricane_graph():
    """Cria e compila o grafo de tracking de furacões"""
    workflow = StateGraph(HurricaneState)
    workflow.add_node("fetch", fetch_hurricane_data)
    workflow.add_node("summarize", summarize_storms)
    workflow.set_entry_point("fetch")
    workflow.add_edge("fetch", "summarize")
    workflow.add_edge("summarize", END)
    return workflow.compile()


# --- Execução ---
def main():
    """Função principal de execução"""
    question = "Quais furacões estão ativos neste momento?"

    logger.info(f"Iniciando análise: {question}")
    print(f"\n🔍 Pergunta: {question}\n")

    graph = create_hurricane_graph()

    try:
        result = graph.invoke({
            "question": question,
            "storms_data": [],
            "synthesis": "",
            "error": None
        })

        print("\n" + "="*60)
        print("🌪️  RELATÓRIO DE TEMPESTADES TROPICAIS")
        print("="*60)
        print(result["synthesis"])
        print("="*60 + "\n")

        if result.get("error"):
            logger.warning(f"Execução finalizada com avisos: {result['error']}")
        else:
            logger.info("Execução finalizada com sucesso")

    except Exception as e:
        logger.error(f"Erro durante execução: {e}")
        print(f"\n❌ Erro: {e}\n")


if __name__ == "__main__":
    main()
