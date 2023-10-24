import sys

from kiteconnect import KiteConnect
from selenium import webdriver
import webbrowser
import time
from pprint import pprint
from datetime import datetime, timedelta
import pandas as pd
import pandas_ta as ta
from tabulate import tabulate
from twilio.rest import Client
from pyotp import TOTP
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
import logging

logging.basicConfig(level=logging.ERROR)

kite = KiteConnect("qszxaz90ed45nqjr")
qty = 50
Trade_Qty = 50
DailyDataDF = pd.DataFrame()

username = "MS5818"
password = "Zerodha@9968"
totp = "WS2WSALVC7YCJQGCUGT27KW43GQNIKWN"
webdriver_path = "./chromedriver"


# url = "https://kite.zerodha.com/"

def AutomatedLogin():
    global kite
    url = kite.login_url()

    service = webdriver.chrome.service.Service(f'{webdriver_path}/chromedriver.exe')
    service.start()

    options = webdriver.ChromeOptions()
    options = options.to_capabilities()

    driver = webdriver.Remote(service.service_url, options)
    driver.get(url)
    driver.maximize_window()

    user = driver.find_element("xpath", "//input[@type = 'text']")
    user.send_keys(username)

    # input password
    pwd = driver.find_element("xpath", "//input[@type = 'password']")
    pwd.send_keys(password)

    # click on login
    driver.find_element("xpath", "//button[@type='submit']").click()

    time.sleep(1)

    # input totp
    ztotp = driver.find_element("xpath", "//input[@type = 'text']")
    totp_token = TOTP(totp)
    token = totp_token.now()
    ztotp.send_keys(token)

    # click on continue
    driver.find_element("xpath", "//button[@type = 'submit']").click()
    time.sleep(20)

    turl = driver.current_url
    print(turl)
    initialtoken = turl.split('request_token=', )[1]
    request_token = initialtoken.split('&')[0]
    print(request_token)

    # Get the access_token
    data = kite.generate_session(request_token, "kznowq2i23fmbu31bw5xyd3gcq9ucvd2")
    access_token = data["access_token"]

    # Use the access_token to make API calls
    kite.set_access_token(access_token)
    print("Access Token Generated")


'''def login():
    global kite
    # Generate the login url
    login_url = kite.login_url()
    print(login_url)

    webbrowser.open_new(login_url)
    # Redirect the user to the login url obtained
    # from kite.login_url(), and receive the request_token
    # from the registered redirect url
    request_token = input("Enter the request tokekn  ")

    # Get the access_token
    data = kite.generate_session(request_token, "kznowq2i23fmbu31bw5xyd3gcq9ucvd2")
    access_token = data["access_token"]

    # Use the access_token to make API calls
    kite.set_access_token(access_token)
    print("Access Token Generated")'''


def quote(token):
    a = kite.quote(token)
    return a[token]['last_price']


def alert(msg, exit_flag):
    account_sid = 'ACc6d2d47e7f03770e26ad2956b05d2fc4'
    auth_token = '46cd6f64778c88f67dee52838fd35241'
    #client = Client(account_sid, auth_token)
    pprint(msg)

    '''message = client.messages.create(
        from_='whatsapp:+14155238886',
        body=msg,
        to='whatsapp:+919953839799'
    )

    print(message.sid)'''

    if exit_flag == True:
        sys.exit()


def hours_minutes_till_target_time(Ttime):
    now = datetime.now()
    target_time = datetime.strptime(Ttime, "%H:%M").time()
    target_datetime = datetime.combine(now, target_time)

    if now.time() > target_time:
        target_datetime += timedelta(days=1)
    time_left = target_datetime - now
    hours, remainder = divmod(int(time_left.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    print("{} hours and {} minutes left till {} AM".format(hours, minutes, Ttime))

    while time_left.total_seconds() > 0:
        time_left = target_datetime - datetime.now()
        hours, remainder = divmod(int(time_left.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        print("{} hours and {} minutes remaining...".format(hours, minutes), end='\r')
        time.sleep(1)

    print(f"Woke up, now it's {Ttime} or later")
    alert("Execution Started", False)


def crawl_round(up):
    r = up % 100
    if 25 <= r <= 75:
        up = up - r + 50
    if r < 25:
        up = up - r
    if r > 75:
        up = up - r + 100
    return up


def place_order(symbol, quant, side):
    if side == -1:
        order_transaction_type = kite.TRANSACTION_TYPE_SELL
    if side == 1:
        order_transaction_type = kite.TRANSACTION_TYPE_BUY

    order_id = kite.place_order(tradingsymbol=symbol,
                                exchange=kite.EXCHANGE_NFO,
                                transaction_type=order_transaction_type,
                                quantity=quant,
                                variety=kite.VARIETY_REGULAR,
                                order_type=kite.ORDER_TYPE_MARKET,
                                product=kite.PRODUCT_NRML,
                                validity=kite.VALIDITY_DAY)

    print(f"Order placed successfully. Order ID: {order_id}")
    alert("Order Placed for : " + symbol, False)


def exit_all_positions():
    positions = kite.positions()

    for position in positions['net']:
        if position['quantity'] > 0:
            # If long position, place a sell order to exit
            kite.place_order(variety=kite.VARIETY_REGULAR,
                             exchange=position['exchange'],
                             tradingsymbol=position['tradingsymbol'],
                             transaction_type=kite.TRANSACTION_TYPE_SELL,
                             quantity=abs(position['quantity']),
                             order_type=kite.ORDER_TYPE_MARKET,
                             product=kite.PRODUCT_NRML)
        elif position['quantity'] < 0:
            # If short position, place a buy order to exit
            kite.place_order(variety=kite.VARIETY_REGULAR,
                             exchange=position['exchange'],
                             tradingsymbol=position['tradingsymbol'],
                             transaction_type=kite.TRANSACTION_TYPE_BUY,
                             quantity=abs(position['quantity']),
                             order_type=kite.ORDER_TYPE_MARKET,
                             product=kite.PRODUCT_NRML)


def target_and_stoploss(initiaCE, ce_price, initialPE, pe_price, crawl_expiry):
    # Calculate the overall unrealized profit or loss
    total_pl = (initiaCE - ce_price + initialPE - pe_price) * qty

    utilized_margin = kite.margins()['equity']['utilised']['debits']

    profit_loss_percentage = total_pl / utilized_margin

    if profit_loss_percentage < -0.03:
        print("Stop Loss Hit")
        alert("Stop Loss Hit. Re-Entering the market", False)
        exit_all_positions()

        crawl(crawl_expiry)

    if profit_loss_percentage >= 0.02:
        print("Target Achieved")
        alert("Profit Target Hit.  Creating a new position", False)
        exit_all_positions()

        crawl(crawl_expiry)

    return total_pl, profit_loss_percentage * 100


def storedata(up, upperbarrier, lowerbarrier, pl_total, PL_percentage):
    global DailyDataDF
    data_storage = {"Date": datetime.now().date(),
                    "time": datetime.now().time(),
                    "PE Barrier": [lowerbarrier],
                    "Underlying Price": [up],
                    "CE Barrier": [upperbarrier],
                    "Percentage": [PL_percentage],
                    }

    df = pd.DataFrame(data_storage)

    pd.set_option("display.max_rows", None, "display.max_columns", None)
    DailyDataDF = DailyDataDF.append(df, ignore_index='True')
    print(tabulate(df, headers='keys', tablefmt='psql'))


def fetch_option_positions():
    # Fetch positions
    positions = kite.positions()

    # Find CE and PE positions
    ce_position = None
    pe_position = None
    for position in positions['net']:
        if position['quantity'] < 0 and position['tradingsymbol'][-2:] == 'CE':
            ce_position = position
            ce_strike = int(ce_position['tradingsymbol'][-7:-2])
            ce_expiry = str(ce_position['tradingsymbol'][-12:-7])
        elif position['quantity'] < 0 and position['tradingsymbol'][-2:] == 'PE':
            pe_position = position
            pe_strike = int(pe_position['tradingsymbol'][-7:-2])
            pe_expiry = str(pe_position['tradingsymbol'][-12:-7])

    if ce_position and pe_position:
        # Fetch instrument tokens for CE and PE
        ce_instrument_token = ce_position['instrument_token']
        pe_instrument_token = pe_position['instrument_token']

        # Fetch quotes for CE and PE
        quotes = kite.quote([ce_instrument_token, pe_instrument_token])

        # Extract CE and PE prices, strikes, and expiry dates from quotes and positions
        ce_price = quotes[str(ce_instrument_token)]['last_price']
        pe_price = quotes[str(pe_instrument_token)]['last_price']

        return ce_price, pe_price, ce_strike, pe_strike, ce_expiry
    else:
        print("CE and PE positions not found")
        sys.exit()

def option_chain():
    instruments = kite.instruments

    # Get the current price of Nifty
    nifty_price = next(instrument for instrument in instruments if instrument["symbol"] == "NIFTY")["last_price"]

    # Get the list of at the money calls
    at_the_money_calls = kite.get_instruments(exchange="NSE", symbol="NIFTY", segment="OPTS", optionType="CE",
                                              strikes="ALL")

    # Get the current price of at the money calls
    at_the_money_call_prices = []
    for option in at_the_money_calls:
        if option["strike"] == nifty_price:
            at_the_money_call_prices.append(option["last_price"])

    print(at_the_money_call_prices)

def crawl(expiry=None):
    start_time = datetime.strptime("09:45", "%H:%M").time()
    end_time = datetime.strptime("15:29", "%H:%M").time()

    if start_time <= datetime.now().time() <= end_time:
        underlying_quote = quote("256265")  # 256265 is the token for nifty 50
        up = crawl_round(int(underlying_quote))

        if expiry is None:
            expiry = input("Enter the Expiry Date in YYMDD or YYMMM format")

        for i in ['CE', 'PE']:
            trade_symbol = "NIFTY" + str(expiry) + str(up) + i
            print(trade_symbol)
            place_order(trade_symbol, qty, -1)
            time.sleep(1)

        start_monitoring()

    else:
        print("time is not in between 9:45 AM to 3.30 PM")
        hours_minutes_till_target_time("09:45")  # function for wait and timer till 9.30
        crawl()


def monitor_positions(upperbarrier, lowerbarrier, CEsellprice, PEsellprice):
    try:
        global DailyDataDF

        up = int(quote("256265"))  # 256265 is the token for nifty 50

        ce_price, pe_price, CEstrike, PEstrike, expiry = fetch_option_positions()

        PL_Total, PL_percentage = target_and_stoploss(CEsellprice, ce_price, PEsellprice, pe_price, expiry)

        if up >= upperbarrier or up <= lowerbarrier:
            print("Barriers Broken")
            exit_all_positions()
            time.sleep(2)
            alert("Initiate New Position", True)

            #crawl(expiry)

            #start_monitoring()

    except Exception as e:
        print("An error occurred: ", e)

        if str(e) == "Remote end closed connection without response" or str(
                e) == "('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))":
            print("Connection Error")
            alert("Connection Error", False)
            AutomatedLogin()
            start_monitoring()

        if "Remote end closed connection without response" in str(e):
            print("Checking Connection Error")
            alert("Connection error, restart", False)
            AutomatedLogin()
            start_monitoring()

        if str(e) == "HTTPSConnectionPool(host='api.kite.trade', port=443): Read timed out. (read timeout=7)":
            print("Read Timed Out, Trying again")
            alert("Read Time Out Error Occurred, Attention Required ", False)
            AutomatedLogin()
            start_monitoring()

        if str(e) == "Invalid `api_key` or `access_token`.":
            print('Invalid Access Token or Api Key. Login Again')
            alert("Invalid Access Key, Immediate Attention Required ", False)
            AutomatedLogin()
            start_monitoring()

        if str(e) == "An error occurred: Incorrect `api_key` or `access_token`":
            print('Invalid Access Token or Api Key. Login Again')
            alert("Invalid Access Key, Immediate Attention Required ", False)
            AutomatedLogin()
            start_monitoring()

    storedata(up, upperbarrier, lowerbarrier, PL_Total, PL_percentage)


def start_monitoring():
    start_time = datetime.strptime("09:16", "%H:%M").time()
    end_time = datetime.strptime("15:29", "%H:%M").time()

    try:
        positions = kite.positions()["net"]
        if not positions:
            print("No positions Open Yet")
        else:
            ce_price, pe_price, CEstrike, PEstrike, expiry = fetch_option_positions()

            for pos in positions:
                if pos['quantity'] < 0 and pos['tradingsymbol'][-2:] == 'CE':
                    upperbarrier = int(CEstrike)  # +pos['sell_price'] removed to test strangle instead is straddle
                    CEsellprice = pos['sell_price']
                if pos['quantity'] < 0 and pos['tradingsymbol'][-2:] == 'PE':
                    lowerbarrier = int(PEstrike)  # -pos['sell_price'] removed to test strangle instead is straddle
                    PEsellprice = pos['sell_price']

            alert("Monitoring Started ", False)

            while True:
                if start_time <= datetime.now().time() <= end_time:

                    if datetime.now().second == 0:

                        pos = kite.positions()["net"]

                        if not pos:
                            print("All Positions are closed")
                            break
                        else:
                            monitor_positions(upperbarrier, lowerbarrier, CEsellprice, PEsellprice)


                    else:
                        print("{} seconds remaining...".format(60 - datetime.now().second % 60), end='\r')
                        time.sleep(1)

                else:
                    print("time is not in between 9:16AM to 3.30 PM")
                    hours_minutes_till_target_time("09:16")  # function for wait and timer till 9.30
                    start_monitoring()

    except Exception as e:
        logging.error(f'Error: {e}')
        print("An error occurred:", e)

        if str(e) == "Remote end closed connection without response" or str(
                e) == "('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))":
            print("Connection Error")
            alert("Connection Error", False)
            AutomatedLogin()
            start_monitoring()

        if "Remote end closed connection without response" in str(e):
            print("Checking Connection Error")
            alert("Connection error, restart", False)
            AutomatedLogin()
            start_monitoring()

        if str(e) == "HTTPSConnectionPool(host='api.kite.trade', port=443): Read timed out. (read timeout=7)":
            print("Read Timed Out, Trying again")
            alert("Read Time Out Error Occurred, Attention Required ", False)
            AutomatedLogin()
            start_monitoring()

        if str(e) == "Invalid `api_key` or `access_token`.":
            print('Invalid Access Token or Api Key. Login Again')
            alert("Invalid Access Key, Immediate Attention Required ", False)
            AutomatedLogin()
            start_monitoring()

        if str(e) == "An error occurred: Incorrect `api_key` or `access_token`":
            print('Invalid Access Token or Api Key. Login Again')
            alert("Invalid Access Key, Immediate Attention Required ", False)
            AutomatedLogin()
            start_monitoring()



        '''if isinstance(e, kiteconnect.exceptions.TokenException):
            print("Token Error. Login Again")
            alert("Re-Login Required")
            login()

        if isinstance(e, requests.exceptions.ReadTimeout) or isinstance(e, TimeoutError):
            print("Timeout Error. Restart Monitoring")
            alert("Timeout Error. Restarting Monitoring ")
            start_monitoring()

        if isinstance(e, http.client.RemoteDisconnected):
            print("Remote Disconnected. Restart Monitoring")
            alert("Remote Disconnected Error. Restarting Monitoring ")
            start_monitoring()'''

    #alert("Monitoring Stopped. Immediate Attention Required!", True)
    print("Monitoring Ended")
