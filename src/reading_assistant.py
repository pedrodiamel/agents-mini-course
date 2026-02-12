"""
Reading Assistant Agent using LangGraph
Searches for books and displays covers via Open Library API
"""

import os
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import openai
import requests
import subprocess
from dotenv import load_dotenv, find_dotenv

_ = load_dotenv(find_dotenv())  # read local .env file
openai.api_key = os.environ["OPENAI_API_KEY"]

class AgentState(TypedDict):
    """State of the reading assistant agent"""
    messages: Annotated[list, "The messages in the conversation"]
    search_query: str
    search_results: list
    selected_book: dict
    next_action: str


def search_books(query: str, limit: int = 5) -> list:
    """
    Search for books using Open Library Search API
    """
    try:
        url = "https://openlibrary.org/search.json"
        params = {
            "q": query,
            "limit": limit,
            "fields": "key,title,author_name,first_publish_year,isbn,cover_i,publisher,language"
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        books = []
        for doc in data.get("docs", []):
            book = {
                "title": doc.get("title", "Unknown"),
                "authors": doc.get("author_name", ["Unknown"]),
                "first_publish_year": doc.get("first_publish_year"),
                "key": doc.get("key"),
                "cover_id": doc.get("cover_i"),
                "publishers": doc.get("publisher", []),
                "isbn": doc.get("isbn", [None])[0] if doc.get("isbn") else None
            }
            books.append(book)

        return books
    except Exception as e:
        print(f"Error searching books: {e}")
        return []


def get_cover_url(cover_id: int, size: str = "M") -> str:
    """
    Get cover image URL from Open Library
    Size can be S (small), M (medium), L (large)
    """
    if not cover_id:
        return None
    return f"https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg"


def get_book_details(book_key: str) -> dict:
    """
    Get detailed information about a book
    """
    try:
        url = f"https://openlibrary.org{book_key}.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting book details: {e}")
        return {}


def process_input(state: AgentState) -> AgentState:
    """
    Process user input and determine next action
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    system_msg = SystemMessage(content="""You are a helpful reading assistant.
    Analyze the user's message and determine if they want to:
    1. SEARCH - Search for books
    2. DETAILS - Get details about a specific book
    3. CHAT - General conversation about books

    Respond with just the action type and any extracted query.
    Format: ACTION: <type> | QUERY: <extracted query>""")

    messages = [system_msg] + state["messages"]
    response = llm.invoke(messages)

    content = response.content.upper()

    if "SEARCH" in content:
        query_part = content.split("QUERY:")[-1].strip()
        state["search_query"] = query_part
        state["next_action"] = "search"
    elif "DETAILS" in content:
        state["next_action"] = "details"
    else:
        state["next_action"] = "chat"

    return state


def search_node(state: AgentState) -> AgentState:
    """
    Search for books based on query
    """
    query = state.get("search_query", "")

    if not query:
        state["messages"].append(
            AIMessage(content="Por favor, me diga que tipo de livro você está procurando.")
        )
        state["next_action"] = "end"
        return state

    books = search_books(query)
    state["search_results"] = books

    if not books:
        state["messages"].append(
            AIMessage(content=f"Não encontrei livros para '{query}'. Tente outra busca.")
        )
        state["next_action"] = "end"
        return state

    # Format results
    result_text = f"Encontrei {len(books)} livros sobre '{query}':\n\n"

    for i, book in enumerate(books, 1):
        result_text += f"{i}. **{book['title']}**\n"
        result_text += f"   Autor(es): {', '.join(book['authors'])}\n"
        if book['first_publish_year']:
            result_text += f"   Ano: {book['first_publish_year']}\n"

        if book['cover_id']:
            cover_url = get_cover_url(book['cover_id'])
            result_text += f"   Capa: {cover_url}\n"
            # Open first book cover in browser
            if i == 1:
                try:
                    subprocess.run(['sh', '-c', f'$BROWSER "{cover_url}"'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as e:
                    print(f"Aviso: Não foi possível abrir o navegador: {e}")

        result_text += "\n"

    state["messages"].append(AIMessage(content=result_text))
    state["next_action"] = "end"

    return state


def chat_node(state: AgentState) -> AgentState:
    """
    General chat about books
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

    system_msg = SystemMessage(content="""You are a knowledgeable and friendly reading assistant.
    Help users discover books, provide recommendations, and discuss literature.
    Be conversational and enthusiastic about books.
    Respond in Portuguese (Brazilian).""")

    messages = [system_msg] + state["messages"]
    response = llm.invoke(messages)

    state["messages"].append(AIMessage(content=response.content))
    state["next_action"] = "end"

    return state


def route_action(state: AgentState) -> Literal["search", "chat", "end"]:
    """
    Route to next node based on action
    """
    action = state.get("next_action", "end")

    if action == "search":
        return "search"
    elif action == "chat":
        return "chat"
    else:
        return "end"


def create_reading_assistant() -> StateGraph:
    """
    Create the reading assistant graph
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("process_input", process_input)
    workflow.add_node("search", search_node)
    workflow.add_node("chat", chat_node)

    # Add edges
    workflow.set_entry_point("process_input")

    workflow.add_conditional_edges(
        "process_input",
        route_action,
        {
            "search": "search",
            "chat": "chat",
            "end": END
        }
    )

    workflow.add_edge("search", END)
    workflow.add_edge("chat", END)

    return workflow.compile()


def main():
    """
    Main function to run the reading assistant
    """
    print("=== Reading Assistant ===")
    print("Assistente de leitura com Open Library")
    print("Digite 'sair' para encerrar\n")

    agent = create_reading_assistant()
    conversation_history = []

    while True:
        user_input = input("Você: ").strip()

        if user_input.lower() in ["sair", "exit", "quit"]:
            print("Até logo! Boa leitura! 📚")
            break

        if not user_input:
            continue

        conversation_history.append(HumanMessage(content=user_input))

        state = {
            "messages": conversation_history.copy(),
            "search_query": "",
            "search_results": [],
            "selected_book": {},
            "next_action": ""
        }

        try:
            result = agent.invoke(state)

            # Get last AI message
            ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
            if ai_messages:
                last_response = ai_messages[-1].content
                print(f"\nAssistente: {last_response}\n")
                conversation_history.append(AIMessage(content=last_response))

        except Exception as e:
            print(f"\nErro: {e}\n")


if __name__ == "__main__":
    main()