# Vou deixar algumas OBS para auxiliar o entendimento do código =)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from youtube_transcript_api import YouTubeTranscriptApi
from requests import Session
import re

app = FastAPI()

# Começo configurando quais sites podem usufruir do código, e as requisições que podem ser aceitas:

# OBS_{1}: As configurações a seguir podem não parecer tão importantes agora, mas podem ajudar caso esse código venha a ficar maior.

app.add_middleware(
    CORSMiddleware,

    # O site que pede uma legenda (origin) está representado aqui:
    allow_origins=["*"], # OBS_{2}: Nesse caso, estou permitindo qualquer site pois ainda não sei o endereço do front-end.
    # Exemplo: Se o front-end estiver em: "http://localhost:4000", você pode colocar essa string no lugar de "*".

    # Na próxima linha, posso configurar quais "verbos" HTTP o site pode acessar.
    # Bom, nesse código só temos um verbo GET. 
    # Mas para facilitar caso hajam modificações futuras no código, permito todos os "verbos":
    allow_methods=["*"],

    # O Front-End pode querer enviar informações extras(como tokens de login ou um arquivo JSON).
    # Sei que não é o caso nessa fase inicial, mas novamente, apenas por precaução, pode ser interessante permitir tudo:
    allow_headers=["*"],
)

# Vou criar uma sessão para guardar os arquivos de Cookies que o Youtube pode mandar.
# Isso faz com que o Youtube permita múltiplas requisições de legenda e não bloqueie:
session = Session()

# Agora, podemos começar recebendo a URL, e limpando ela:

def limpar_url_extrair_id(url: str):
    # Existem três tipos principais de sufixos de links do Youtube:

    # Links normais: v=
    # Links de vídeos curtos(Shorts): / 
    # Links de compartilhamento: be/

    # Usei ?: para buscar por esses padrões. Por isso, até agora temos (?:v=|/|be/).
    # Depois disso, vem a parte importante do link, que é o ID do vídeo, composto de 11 caracteres.
    # Esses caracteres podem ser qualquer algarismo e qualquer letra de de qualquer capitalização.
    # Por isso, o padrão da URL que procuramos é exatamente esse:
    padrao = r'(?:v=|/|be/)([0-9A-Za-z_-]{11})'

    # Agora, basta buscar por esse padrão na URL dada de entrada:
    encaixou = re.search(padrao, url)
    # Nesse momento, tem 2 possibilidades:
    # 1 - A URL se encaixa no padrão:
    #   Então, encaixou.group(0) vai ser o padrão todo (?:v=|/|be/)([0-9A-Za-z_-]{11}) (exemplo: v=jNQXAC9IVRw)
    #   Além disso, encaixou.group(1) vai ser somente ([0-9A-Za-z_-]{11}) (no exemplo: jNQXAC9IVRw)
    #   Note que essa última parte é o ID do vídeo que nos interessa.
    # 2 - A URL não se encaixa no padrão:
    #   Então, encaixou vai ser um objeto vazio (reconhecido pelo Python como falso).
    # Isso leva a seguinte a lógica para extrair o ID:

    if encaixou:
        return encaixou.group(1)
    else:
        return None

# Agora, com a URL limpa, posso começar a extrair a legenda do vídeo:
@app.get("/api/legenda")
async def obter_legenda(url: str):
    video_id = limpar_url_extrair_id(url)
    # Se a URL não se encaixou no padrão lá em cima, retorno um erro para o usuário:
    if not video_id:
        raise HTTPException(status_code=400, detail="URL do YouTube inválida.")
    
    # Se encaixou, podemos seguir para as legendas:
    try:
        # Começo usando sessão criada anteriormente com a biblioteca:
        youtube_api = YouTubeTranscriptApi(http_client=session)
        # Aqui, peço por uma lista de todos os tipos de legenda disponíveis para o vídeo com um certo ID.
        lista_de_legendas = youtube_api.list(video_id)
        # Exemplo: Poderia retornar a lista = [Inglês(gerada automaticamente), Inglês(manual), Português(gerada automaticamente)]
        
        # Mas, nosso interesse aqui são as legendas manuais em inglês.
        # Procuremos por elas:
        legenda_manual_ingles = lista_de_legendas.find_manually_created_transcript(['en'])
        
        # Agora sim, podemos propriamente baixar as legendas do vídeo:
        blocos_de_legenda = legenda_manual_ingles.fetch()
        # Esse método faz o seguinte:
        # Baixa a legenda, e a organiza como se fosse uma lista de objetos.

        # Cada objeto desse é um "bloco" da legenda, que possui os seguintes atributos:

        # bloco.text: A legenda propriamente dita daquele momento do vídeo.
        # bloco.start: A marcação de tempo quando essa legenda apareceu no vídeo.
        # bloco.duration: Quanto tempo essa legenda ficará na tela, até dar espaço para a próxima.
        
        # Contudo, esses blocos ainda precisam ser formatados. É isso que seria feito agora:
        # Começo criando um array de legendas_formatadas:
        legendas_formatadas = []
        for bloco in blocos_de_legenda:
            # Eu obtive algumas strings indesejáveis com \n, por exemplo: "All right, so\nelephants"
            # A string correta deveria ser: "All right, so elephants"
            # Para corrigir isso, o método split() considera tanto espaços quanto \n como separadores.
            # Logo, para essa string de exemplo, ele retorna: ["All", "right,", "so", "elephants"]
            # Isso remove o \n. Agora, o método join() une todas as strings, com um espaço de distância entre elas.
            # Então, temos o resultado desejado. No exemplo: "All right, so elephants"
            texto_limpo = " ".join(bloco.text.split())

            # Agora basta adicionar esse bloco de legenda formatado na lista de blocos, com todos seus atributos:
            legendas_formatadas.append({
                "texto": texto_limpo,      
                "inicio": bloco.start,    
                "duracao": bloco.duration 
            })

        # Para finalizar, retorno o ID do vídeo em questão, o idioma da legenda, e a lista de blocos de legenda formatados:   
        return legendas_formatadas

    except Exception as e:
        mensagem_de_erro = str(e)
        # Se a legenda manual em inglês não for encontrada, retorno o erro:
        if "No transcript found" in mensagem_de_erro or "Could not find" in mensagem_de_erro:
            raise HTTPException(status_code=404, detail="Vídeo sem legenda manual em inglês.")
        
        # Se outro tipo de erro ocorrer, ele cai nessa categoria:
        print(f"Erro técnico: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar legendas.")
