from langchain_community.tools import WikipediaQueryRun, ArxivQueryRun
from langchain_community.utilities import WikipediaAPIWrapper, ArxivAPIWrapper
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing import TypedDict, List
import os
import openai

# --- Configuração ---
from dotenv import load_dotenv, find_dotenv

_ = load_dotenv(find_dotenv())  # read local .env file
openai.api_key = os.environ["OPENAI_API_KEY"]


# --- Definição do estado ---
class ResearchState(TypedDict):
    question: str
    arxiv_docs: List[str]
    wiki_docs: List[str]
    synthesis: str


# --- Inicialização dos tools ---
wiki_tool = WikipediaQueryRun(
    api_wrapper=WikipediaAPIWrapper(
        lang="pt", top_k_results=2, doc_content_chars_max=4000
    )
)
arxiv_tool = ArxivQueryRun(api_wrapper=ArxivAPIWrapper(max_results=3))
llm = ChatOpenAI(model="gpt-4o-mini")


# --- Etapas do LangGraph ---
def search_arxiv(state: ResearchState):
    query = state["question"]
    print(f"🔍 Buscando artigos no arXiv sobre: {query}")
    result = arxiv_tool.run(query)
    return {"arxiv_docs": [result]}


def search_wikipedia(state: ResearchState):
    query = state["question"].strip()
    if not query:
        raise ValueError(
            "❌ Pergunta vazia: o parâmetro 'srsearch' precisa de um termo de busca válido."
        )
    print(f"📘 Buscando contexto na Wikipedia: {query}")
    try:
        result = wiki_tool.run(query)
    except Exception as e:
        print(f"⚠️ Erro na Wikipedia API: {e}")
        result = "Não foi possível obter resultados da Wikipedia."
    return {"wiki_docs": [result]}


def synthesize_answer(state: ResearchState):
    print("🧠 Gerando síntese final...\n")
    print("📝 ", end="", flush=True)
    context = "\n\n".join(state["arxiv_docs"] + state["wiki_docs"])
    prompt = f"""
    Você é um pesquisador científico.
    Pergunta: {state['question']}
    Fontes:
    {context}

    Gere uma resposta clara, com ênfase em descobertas recentes, conceitos centrais e implicações.
    """

    # Streaming da resposta
    full_answer = ""
    for chunk in llm.stream(prompt):
        content = chunk.content
        print(content, end="", flush=True)
        full_answer += content

    print("\n")  # Nova linha após streaming
    return {"synthesis": full_answer}


# --- Construção do grafo ---
workflow = StateGraph(ResearchState)
workflow.add_node("arxiv_search", search_arxiv)
workflow.add_node("wiki_search", search_wikipedia)
workflow.add_node("synthesis", synthesize_answer)

workflow.set_entry_point("arxiv_search")
workflow.add_edge("arxiv_search", "wiki_search")
workflow.add_edge("wiki_search", "synthesis")
workflow.add_edge("synthesis", END)

graph = workflow.compile()

# --- Execução ---
if __name__ == "__main__":
    print("🔬 Assistente de Pesquisa Científica (Modo Streaming)")
    print("Digite 'sair' ou 'exit' para encerrar\n")

    while True:
        query = input("\n💬 Digite sua pergunta científica: ").strip()

        if query.lower() in ["sair", "exit", "quit", ""]:
            print("\n👋 Até logo!")
            break

        try:
            print("\n" + "=" * 60)

            # Usar streaming do grafo para ver cada etapa em tempo real
            for event in graph.stream({"question": query}):
                # Cada event é um dict com o nome do nó como chave
                for node_name, node_output in event.items():
                    if node_name == "arxiv_search":
                        print(
                            f"✅ arXiv: {len(node_output.get('arxiv_docs', [''])[0])} caracteres coletados"
                        )
                    elif node_name == "wiki_search":
                        print(
                            f"✅ Wikipedia: {len(node_output.get('wiki_docs', [''])[0])} caracteres coletados"
                        )
                    elif node_name == "synthesis":
                        # A síntese já é impressa no streaming interno do LLM
                        pass

            print("=" * 60)
        except Exception as e:
            print(f"\n❌ Erro ao processar pergunta: {e}")
            print("Tente novamente com outra pergunta.")
