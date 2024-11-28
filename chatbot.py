import random
from datetime import datetime

from chat import Session as ChatSession, Context, Initiator
from requests import Session as NetworkSession
from bot import Bot, command, listener
from jokes import jokes as local_jokes

class ChatBot(Bot):
    """
    ChatBot
    ---
    A simple chatbot implementation Using Bot as its base
    """
    def __init__(self, chat_session: ChatSession = None, network_session: NetworkSession = None):
        super().__init__(chat_session, initiator=Initiator.ChatBot, name=Initiator.ChatBot, case_sensitive=False)
        self.network_session = network_session
    
    @listener("on_message")
    def on_message(self, ctx: Context):
        print("[{}] Received a message from {}: {}".format(ctx.message.datetime.isoformat(), ctx.message._from, ctx.message.content))
    
    @command("halo", "hai", "hello", "oi", "helo", "hi", "hei", description="Greet the bot")
    def greet_handler(self, ctx: Context):
        responses = ["Halo", "Apa kabar?", "Hari yang indah bukan?", "Hei!", "Hai!", "Salam!", "Bagaimanakah hidup?", "Bagaimana kabar Anda?"]
        response = random.choice(responses)
        ctx.send_message(content=response)
        
        def response_handler(ctx: Context):
            msg = ctx.message.content.lower().strip()
            if any([e in msg for e in "buruk,jelek,terrible,worst,tidak".split(',')]):
                ctx.send_message(content="Semoga hari anda berjalan lebih baik!")
            else:
                ctx.send_message(content="Kabar yang bagus!")
        
        if response.endswith("?"):
            return response_handler
    
    @command("perkenalkan diri", "siapa anda", "siapakah anda", "siapa kamu", "intro", "introduce", "introduce yourself", description="Introduce the bot")
    def introduce_self(self, ctx: Context):
        ctx.send_message(content="Perkenalkan saya adalah ChatBot pendamping anda, peran saya dalam program ini adalah sebagai pelaksana perintah anda. Silahkan berikan perintah apapun!")
    
    @command("beri lelucon", "buat lelucon", "berikan lelucon", "give joke", "gimme joke", description="Generate a random joke")
    def joke_handler(self, ctx: Context):
        reply = "Sorry, something went wrong :("
        try:
            if random.randint(1,2) == 1:
                resp = self.network_session.get(
                    "https://v2.jokeapi.dev/joke/Any", 
                    params={
                        'blacklistFlags':'nsfw,religious,political,racist,sexist,explicit', 
                        'type':'single'
                })
                if resp.ok:
                    reply = resp.json()['joke']
            else:
                reply = random.choice(local_jokes)
        except:
            pass
        ctx.send_message(content=reply)
    
    @command("tanya waktu", "tanya jam", "ini jam", "jam berapa", "ini jam berapa", description="Ask the current local time")
    def time_handler(self, ctx: Context):
        ctx.send_message(content=datetime.now().strftime("Saat ini pukul %H:%M:%S."))
    
    @command("soal math", "soal matek", "beri soal math", "beri soal matematika", "beri soal matek", "beri aku soal matematika", description="Generate a simple math question")
    def math_handler(self, ctx: Context):
        a = random.randint(1, 30)
        b = random.randint(1, 30)
        operation, ans = random.choice([('+', a+b), ('-', a-b), ('*', a*b)])
        ctx.send_message(content="Apa hasil dari {}{}{}?".format(a, operation, b))
        
        def response_handler(ctx: Context):
            msg = ctx.message.content.strip()
            if not (msg.isdigit() or (msg[1:].isdigit() and msg[0]=='-')):
                ctx.send_message(content="Masukkan angka yang valid sebagai jawaban.")
                return response_handler
            
            reply = "Salah, jawaban yang benar adalah {}.".format(ans)
            if msg == str(ans).strip():
                reply = "Benar! Jawabanmu tepat. 😊"
            ctx.send_message(content=reply)
        
        return response_handler
    
    @command('xyz', description="Example Unimplemented command")
    def xyz_handler(self, ctx: Context):
        ctx.send_message(content="Fungsi ini belum diimplementasikan.")
    
    @command('pick one', 'random', description="Picks a random item from the given choices")
    def pick_one(self, ctx: Context, *, choices):
        ctx.send_message(content="I pick {}".format(random.choice(choices.split())))
    
    # Simple command example
    @command('ping', description="Sends a ping to the bot")
    def ping(self, ctx):
        ctx.send_message(content='pong')
    
    # Simple echo command, introducing greedy params
    @command('echo', description="Echoes back what you said")
    def echo(ctx, *, message):
        ctx.send_message(content='You said: {}'.format(message))
    
    # Continuous command flow example
    @command('guess game', description="Guess a number within the allocated tries to win. Configure number range through lowerbound and higherbound")
    def guess_game(self, ctx, lowerbound: int = 1, higherbound: int = 100):
        answer = random.randint(lowerbound, higherbound)
        tries_left = 5
        ctx.send_message(content="Start guessing a number between {} and {}".format(lowerbound, higherbound))
        def response_handler(ctx):
            nonlocal tries_left
            msg = ctx.message.content.strip()
            tries_left -= 1
            if not msg.isdigit():
                ctx.send_message(content="Invalid number, you have {} tries left.".format(tries_left))
                return response_handler
            num = int(msg)
            if num == answer:
                ctx.send_message(content="Congratulations, You guessed correctly!")
                return
            if tries_left==0:
                ctx.send_message(content="You failed to guess the correct number, the answer is {}".format(answer))
                return
            
            if num < answer:
                ctx.send_message(content="Higher! ({} tries left)".format(tries_left))
            if num > answer:
                ctx.send_message(content="Lower! ({} tries left)".format(tries_left))
            return response_handler
        return response_handler
    
    @command('8ball', '8 ball', description="Ask your question and let the 8ball decide for you!")
    def _8ball(self, ctx: Context, *, question):
        responses = [
            'It is certain.', 'It is decidedly so.', 'Without a doubt.', 'Yes, definitely.',
            'You may rely on it.', 'As I see it, yes.', 'Most likely.', 'Outlook good.', 'Yes.',
            'Signs point to yes.', 'Reply hazy, try again.', 'Ask again later.', 'Better not tell you now.',
            'Cannot predict now.', 'Concentrate and ask again.', "Don't count on it.", 'My reply is no.',
            'My sources say no.', 'Outlook not so good.', 'Very doubtful.']
        ctx.send_message(content=f"Question: {question} \nAnswer: {random.choice(responses)}")
