import requests
from bs4 import BeautifulSoup
import re
import statistics
import openai
from os import environ
import tkinter as tk
from tkinter import scrolledtext, messagebox

openai.api_key = environ.get('OPENAI_API_KEY')  

class eBayAnalysisAgent:
    def __init__(self):
        pass

    def generate_sold_listings_url(self, search_keywords, new=False):
        base_url = "https://www.ebay.com/sch/i.html?_from=R40&_nkw="
        sold_listings_params = "&_sacat=0&rt=nc&LH_Sold=1&LH_Complete=1"
        new_condition_param = "&LH_ItemCondition=1000"
        search_keywords = search_keywords.replace(' ', '+')
        sold_url = base_url + search_keywords + sold_listings_params
        if new:
            sold_url += new_condition_param
        return sold_url

    def generate_live_listings_url(self, search_keywords, new=False):
        base_url = "https://www.ebay.com/sch/i.html?_from=R40&_nkw="
        listed_listings_params = "&_sacat=0&rt=nc"
        new_condition_param = "&LH_ItemCondition=1000"
        search_keywords = search_keywords.replace(' ', '+')
        listed_url = base_url + search_keywords + listed_listings_params
        if new:
            listed_url += new_condition_param
        return listed_url

    def fetch_data(self, url):
        response = requests.get(url)
        if response.status_code == 200:
            return response.content
        return None

    def parse_data(self, content):
        soup = BeautifulSoup(content, 'html.parser')
        title_divs = soup.find_all('div', class_='s-item__title')
        titles = [div.span.get_text() for div in title_divs if div.span]
        prices = [item.get_text() for item in soup.find_all('span', class_='s-item__price')]
        return list(zip(titles, prices))

    def extract_price_from_string(self, price_string):
        match = re.search(r'(\d+\.\d+)', price_string)
        if match:
            return float(match.group(1))
        return None

    def analyze_title(self, title, new=False):
        if 'new' in title.lower():
            new = True
        sold_url = self.generate_sold_listings_url(title, new)
        live_url = self.generate_live_listings_url(title, new)
        
        sold_content = self.fetch_data(sold_url)
        live_content = self.fetch_data(live_url)
        
        sold_listings = self.parse_data(sold_content)
        live_listings = self.parse_data(live_content)
        
        # Filter out the 'Shop on eBay' listing
        sold_listings = [listing for listing in sold_listings if listing[0] != 'Shop on eBay']
        live_listings = [listing for listing in live_listings if listing[0] != 'Shop on eBay']

        # Extract prices and calculate average for sold listings
        sold_prices = [self.extract_price_from_string(price) for _, price in sold_listings]
        avg_sold_price = statistics.mean(sold_prices) if sold_prices else 0

        # Prepare data for GPT-4
        data_summary = f"""
        Sold Listings Average Price: ${avg_sold_price:.2f}
        Sold Listings Details: {sold_listings[:10]}
        Live Listings Details: {live_listings[:10]}
        """

        # Send Data to GPT-4
        prompt = f"""
        I am going to provide you with some recent sales data and live listing data from eBay in order for you to help me price a similar item. 
        Make sure if the item is a lot you compare it to similar lots with a similar amount of items. 
        Can you analyze the following data and come up with a fair price?
        {data_summary}
        """

        # Make the API call
        response = openai.Completion.create(
        prompt=prompt,
        model="gpt-3.5-turbo-instruct",
        max_tokens=150,
        temperature=0,)   
        
        # Extract the response text
        gpt3_response = response['choices'][0]['text']

        return {
            'average_sold_price': avg_sold_price,
            'gpt4_analysis': gpt3_response
        }

class AnalysisApp(tk.Tk):
    def __init__(self, agent):
        super().__init__()
        self.agent = agent
        self.title("eBay Analysis Agent")
        self.geometry("600x400")
        
        self.welcome_label = tk.Label(self, text="Welcome to the eBay Analysis Agent!")
        self.welcome_label.pack(pady=10)

        self.label = tk.Label(self, text="Enter a title for analysis:")
        self.label.pack(pady=10)

        self.title_entry = tk.Entry(self, width=50)
        self.title_entry.pack(pady=10)

        self.analyze_button = tk.Button(self, text="Analyze", command=self.on_analyze_button_click)
        self.analyze_button.pack(pady=10)

        self.results_text = scrolledtext.ScrolledText(self, width=70, height=10)
        self.results_text.pack(pady=10)

        # Bind the Enter key to the on_enter_key method
        self.bind('<Return>', self.on_enter_key)

    def on_analyze_button_click(self):
        title = self.title_entry.get()
        if not title:
            messagebox.showerror("Error", "Please enter a title.")
            return

        results = self.agent.analyze_title(title)

        # Display the results in the scrolledtext widget
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, f"Average Sold Price: ${results['average_sold_price']:.2f}\n")
        self.results_text.insert(tk.END, "\nGPT-4 Analysis:\n----------------\n")
        self.results_text.insert(tk.END, results['gpt4_analysis'])

    def on_enter_key(self, event=None):
        self.on_analyze_button_click()

if __name__ == "__main__":
    agent = eBayAnalysisAgent()
    app = AnalysisApp(agent)
    app.mainloop()
