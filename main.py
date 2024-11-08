import asyncio
import ctypes
import random
import sys
import traceback
from threading import Thread

from art import text2art
from imap_tools import MailboxLoginError
from termcolor import colored, cprint
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.lang import Builder

from better_proxy import Proxy

from core import Grass
from core.autoreger import AutoReger
from core.utils import logger, file_to_list
from core.utils.accounts_db import AccountsDB
from core.utils.exception import EmailApproveLinkNotFoundException, LoginException, RegistrationException
from core.utils.generate.person import Person
from data.config import ACCOUNTS_FILE_PATH, PROXIES_FILE_PATH, REGISTER_ACCOUNT_ONLY, THREADS, REGISTER_DELAY, \
    CLAIM_REWARDS_ONLY, APPROVE_EMAIL, APPROVE_WALLET_ON_EMAIL, MINING_MODE, CONNECT_WALLET, \
    WALLETS_FILE_PATH, SEND_WALLET_APPROVE_LINK_TO_EMAIL, SINGLE_IMAP_ACCOUNT, SEMI_AUTOMATIC_APPROVE_LINK

Builder.load_string('''
<MainScreen>:
    orientation: 'vertical'
    padding: 10
    spacing: 10
    
    BoxLayout:
        size_hint_y: None
        height: '48dp'
        spacing: 10
        
        Button:
            id: start_button
            text: 'Start'
            on_press: root.start_script()
        
        Button:
            id: stop_button
            text: 'Stop'
            on_press: root.stop_script()
            disabled: True
    
    ScrollView:
        Label:
            id: log_output
            size_hint_y: None
            height: self.texture_size[1]
            text_size: self.width, None
            padding: 10, 10
''')

class LogHandler:
    def __init__(self, callback):
        self.callback = callback
    def write(self, text):
        self.callback(text)
    def flush(self):
        pass

def bot_info(name: str = ""):
    cprint(text2art(name), 'green')

    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetConsoleTitleW(f"{name}")

    print(
        f"{colored('EnJoYeR <crypto/> moves:', color='light_yellow')} "
        f"{colored('https://t.me/+tdC-PXRzhnczNDli', color='light_green')}"
    )

class MainScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.script_running = False
        self.script_task = None
        self.loop = None
        
        def log_callback(text):
            self.ids.log_output.text += text
        
        sys.stdout = LogHandler(log_callback)
        sys.stderr = LogHandler(log_callback)

    def start_script(self):
        if not self.script_running:
            self.script_running = True
            self.ids.start_button.disabled = True
            self.ids.stop_button.disabled = False
            self.loop = asyncio.new_event_loop()
            
            def run_script():
                asyncio.set_event_loop(self.loop)
                self.loop.run_until_complete(main())
                
            self.script_task = Thread(target=run_script)
            self.script_task.start()

    def on_stop(self):
        if hasattr(self.root, 'loop') and self.root.loop:
            async def cleanup():
                tasks = [task for task in asyncio.all_tasks(self.root.loop) 
                        if task is not asyncio.current_task()]
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                
            if self.root.loop.is_running():
                self.root.loop.create_task(cleanup())
                self.root.loop.stop()



class GrassApp(App):
    def build(self):
        Window.size = (800, 600)
        return MainScreen()

async def worker_task(_id, account: str, proxy: str = None, wallet: str = None, db: AccountsDB = None):
    consumables = account.split(":")[:3]
    imap_pass = None
    
    if SINGLE_IMAP_ACCOUNT:
        consumables.append(SINGLE_IMAP_ACCOUNT.split(":")[1])

    if len(consumables) == 1:
        email = consumables[0]
        password = Person().random_string(8)
    elif len(consumables) == 2:
        email, password = consumables
    else:
        email, password, imap_pass = consumables

    grass = None

    try:
        grass = Grass(_id, email, password, proxy, db)

        if MINING_MODE:
            await asyncio.sleep(random.uniform(1, 2) * _id)
            logger.info(f"Starting №{_id} | {email} | {password} | {proxy}")
        else:
            await asyncio.sleep(random.uniform(*REGISTER_DELAY))
            logger.info(f"Starting №{_id} | {email} | {password} | {proxy}")

        if REGISTER_ACCOUNT_ONLY:
            await grass.create_account()
        elif APPROVE_EMAIL or CONNECT_WALLET or SEND_WALLET_APPROVE_LINK_TO_EMAIL or APPROVE_WALLET_ON_EMAIL:
            await grass.enter_account()

            user_info = await grass.retrieve_user()

            if APPROVE_EMAIL:
                if user_info['result']['data'].get("isVerified"):
                    logger.info(f"{grass.id} | {grass.email} email already verified!")
                else:
                    if SEMI_AUTOMATIC_APPROVE_LINK:
                        imap_pass = "placeholder"
                    elif imap_pass is None:
                        raise TypeError("IMAP password is not provided")
                    await grass.confirm_email(imap_pass)
            if CONNECT_WALLET:
                if user_info['result']['data'].get("walletAddress"):
                    logger.info(f"{grass.id} | {grass.email} wallet already linked!")
                else:
                    await grass.link_wallet(wallet)

            if user_info['result']['data'].get("isWalletAddressVerified"):
                logger.info(f"{grass.id} | {grass.email} wallet already verified!")
            else:
                if SEND_WALLET_APPROVE_LINK_TO_EMAIL:
                    await grass.send_approve_link(endpoint="sendWalletAddressEmailVerification")
                if APPROVE_WALLET_ON_EMAIL:
                    if SEMI_AUTOMATIC_APPROVE_LINK:
                        imap_pass = "placeholder"
                    elif imap_pass is None:
                        raise TypeError("IMAP password is not provided")
                    await grass.confirm_wallet_by_email(imap_pass)
        elif CLAIM_REWARDS_ONLY:
            await grass.claim_rewards()
        else:
            await grass.start()

        return True
    except (LoginException, RegistrationException) as e:
        logger.warning(f"{_id} | {e}")
    except MailboxLoginError as e:
        logger.error(f"{_id} | {e}")
    except EmailApproveLinkNotFoundException as e:
        logger.warning(e)
    except Exception as e:
        logger.error(f"{_id} | not handled exception | error: {e} {traceback.format_exc()}")
    finally:
        if grass:
            await grass.session.close()

async def main():
    accounts = file_to_list(ACCOUNTS_FILE_PATH)

    if not accounts:
        logger.warning("No accounts found!")
        return

    proxies = [Proxy.from_str(proxy).as_url for proxy in file_to_list(PROXIES_FILE_PATH)]

    db = AccountsDB('data/proxies_stats.db')
    await db.connect()

    for i, account in enumerate(accounts):
        account = account.split(":")[0]
        proxy = proxies[i] if len(proxies) > i else None

        if await db.proxies_exist(proxy) or not proxy:
            continue

        await db.add_account(account, proxy)

    await db.delete_all_from_extra_proxies()
    await db.push_extra_proxies(proxies[len(accounts):])

    autoreger = AutoReger.get_accounts(
        (ACCOUNTS_FILE_PATH, PROXIES_FILE_PATH, WALLETS_FILE_PATH),
        with_id=True,
        static_extra=(db, )
    )

    threads = THREADS

    if REGISTER_ACCOUNT_ONLY:
        msg = "__REGISTER__ MODE"
    elif APPROVE_EMAIL or CONNECT_WALLET or SEND_WALLET_APPROVE_LINK_TO_EMAIL or APPROVE_WALLET_ON_EMAIL:
        if CONNECT_WALLET:
            wallets = file_to_list(WALLETS_FILE_PATH)
            if len(wallets) == 0:
                logger.error("Wallet file is empty")
                return
            elif len(wallets) != len(accounts):
                logger.error("Wallets count != accounts count")
                return
        msg = "__APPROVE__ MODE"
    elif CLAIM_REWARDS_ONLY:
        msg = "__CLAIM__ MODE"
    else:
        msg = "__MINING__ MODE"
        threads = len(autoreger.accounts)

    logger.info(msg)

    await autoreger.start(worker_task, threads)

    await db.close_connection()

if __name__ == "__main__":
    bot_info("GRASS_AUTO")
    GrassApp().run()