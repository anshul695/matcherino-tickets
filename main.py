import os
import json
import random
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# Initialize bot
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='%', intents=intents)

# Data storage
class JSONDatabase:
    def __init__(self):
        self.users_file = DATA_DIR / "users.json"
        self.points_file = DATA_DIR / "points.json"
        self.transactions_file = DATA_DIR / "transactions.json"
        self.purchases_file = DATA_DIR / "purchases.json"
        self._initialize_files()

    def _initialize_files(self):
        for file in [self.users_file, self.points_file, self.transactions_file, self.purchases_file]:
            if not file.exists():
                with open(file, 'w') as f:
                    json.dump({}, f)

    def _read_data(self, file: Path) -> Dict:
        with open(file, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    def _write_data(self, file: Path, data: Dict):
        with open(file, 'w') as f:
            json.dump(data, f, indent=4)

    async def get_user(self, user_id: int) -> Dict:
        data = self._read_data(self.users_file)
        return data.get(str(user_id), {})

    async def create_user(self, user_id: int) -> Dict:
        data = self._read_data(self.users_file)
        user_data = {
            "tokens": 0,
            "points": 0,
            "total_words": 0,
            "passes": [],
            "last_points_reset": None,
            "last_token_claim": None
        }
        data[str(user_id)] = user_data
        self._write_data(self.users_file, data)
        return user_data

    async def update_user(self, user_id: int, update_data: Dict):
        data = self._read_data(self.users_file)
        if str(user_id) not in data:
            await self.create_user(user_id)
            data = self._read_data(self.users_file)
        
        data[str(user_id)].update(update_data)
        self._write_data(self.users_file, data)

    async def get_points(self, user_id: int) -> int:
        data = self._read_data(self.points_file)
        return data.get(str(user_id), 0)

    async def add_points(self, user_id: int, points: int):
        data = self._read_data(self.points_file)
        current = data.get(str(user_id), 0)
        data[str(user_id)] = current + points
        self._write_data(self.points_file, data)

        # Update total words in user data
        user_data = await self.get_user(user_id)
        await self.update_user(user_id, {"total_words": user_data.get("total_words", 0) + (points * 5)})

    async def record_transaction(self, user_id: int, amount: int, reason: str):
        data = self._read_data(self.transactions_file)
        if str(user_id) not in data:
            data[str(user_id)] = []
        
        transaction = {
            "amount": amount,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
            "balance": (await self.get_user(user_id)).get("tokens", 0)
        }
        data[str(user_id)].append(transaction)
        self._write_data(self.transactions_file, data)

    async def record_purchase(self, user_id: int, item_name: str, price: int):
        data = self._read_data(self.purchases_file)
        if str(user_id) not in data:
            data[str(user_id)] = []
        
        purchase = {
            "item": item_name,
            "price": price,
            "timestamp": datetime.utcnow().isoformat()
        }
        data[str(user_id)].append(purchase)
        self._write_data(self.purchases_file, data)

# Initialize database
db = JSONDatabase()

# Shop items and passes
SHOP_ITEMS = {
    # PayPal Rewards
    "15$ Paypal": {"price": 37500, "category": "PayPal Rewards", "description": "Get $15 PayPal credit"},
    "10$ Paypal": {"price": 25000, "category": "PayPal Rewards", "description": "Get $10 PayPal credit"},
    "5$ Paypal": {"price": 12500, "category": "PayPal Rewards", "description": "Get $5 PayPal credit"},

    # Brawl Stars Rewards
    "Pro Pass": {"price": 60000, "category": "Brawl Stars Rewards", "description": "Brawl Stars Pro Pass"},
    "Brawl Pass Plus": {"price": 27500, "category": "Brawl Stars Rewards", "description": "Brawl Pass Plus"},
    "Brawl Pass": {"price": 17500, "category": "Brawl Stars Rewards", "description": "Regular Brawl Pass"},
    "200 gems skin": {"price": 42500, "category": "Brawl Stars Rewards", "description": "200 gems skin in Brawl Stars"},

    # Discord Rewards
    "Nitro Boost": {"price": 22500, "category": "Discord Rewards", "description": "Discord Nitro Boost"},
    "Nitro Basic": {"price": 8000, "category": "Discord Rewards", "description": "Discord Nitro Basic"},
    "5$ Decoration": {"price": 11000, "category": "Discord Rewards", "description": "$5 Discord decoration"},

    # Promoting
    "@everyone pin": {"price": 5000, "category": "Promoting", "description": "Pin your message with @everyone"},
    "Community ping": {"price": 2500, "category": "Promoting", "description": "Ping the Community role"},
    "Server Promotion": {"price": 17000, "category": "Promoting", "description": "Promote your server"},
    "Social Promotion": {"price": 12500, "category": "Promoting", "description": "Promote your social media"},
    "Content Promotion": {"price": 8750, "category": "Promoting", "description": "Promote your content"},

    # Server Rewards - Roles
    "I am rich.": {"price": 75000, "category": "Server Roles", "description": "Permanent 'I am rich.' role"},
    "Ultra Customer": {"price": 35000, "category": "Server Roles", "description": "Permanent 'Ultra Customer' role"},
    "Big Customer": {"price": 15000, "category": "Server Roles", "description": "Permanent 'Big Customer' role"},
    "Simple Customer": {"price": 5000, "category": "Server Roles", "description": "Permanent 'Simple Customer' role"},

    # Custom roles
    "Add color": {"price": 1500, "category": "Custom Roles", "description": "Add color to your role"},
    "Add icon": {"price": 2500, "category": "Custom Roles", "description": "Add icon to your role"},
    "Displayed separately": {"price": 4000, "category": "Custom Roles", "description": "Display role separately"},
    "Permanent role": {"price": 15000, "category": "Custom Roles", "description": "Make your role permanent"},
    "2 months role": {"price": 8500, "category": "Custom Roles", "description": "Role for 2 months"},
    "2 weeks role": {"price": 2000, "category": "Custom Roles", "description": "Role for 2 weeks"},

    # Stickers/Emojis
    "3 stickers": {"price": 2500, "category": "Stickers/Emojis", "description": "Add 3 stickers to server"},
    "3 emojis": {"price": 2000, "category": "Stickers/Emojis", "description": "Add 3 emojis to server"},
    "1 sticker": {"price": 1000, "category": "Stickers/Emojis", "description": "Add 1 sticker to server"},
    "1 emoji": {"price": 800, "category": "Stickers/Emojis", "description": "Add 1 emoji to server"},

    # Giveaway Entries
    "+1 entry": {"price": 600, "category": "Giveaway Entries", "description": "+1 giveaway entry"},
    "+3 entries": {"price": 1500, "category": "Giveaway Entries", "description": "+3 giveaway entries"},
    "+5 entries": {"price": 2750, "category": "Giveaway Entries", "description": "+5 giveaway entries"},
    "+10 entries": {"price": 5250, "category": "Giveaway Entries", "description": "+10 giveaway entries"},
}

VRT_PASSES = {
    "Club Member": {
        "price": "Free with club membership",
        "monthly_tokens": 1000,
        "giveaway_entries": "+1",
        "discounts": "10% on stickers/emojis & giveaway entries",
        "role": "@Club Member",
        "description": "For Veracity Club members",
        "vrt_price": 0
    },
    "Basic Pass": {
        "price": "$2.99 or 1 boost/month",
        "monthly_tokens": 6000,
        "giveaway_entries": "+2",
        "discounts": "10% in Server Rewards",
        "role": "None",
        "description": "Entry-level pass",
        "vrt_price": 0  # Can't be bought with VRT
    },
    "VRT Pass": {
        "price": "$4.99 or 2 boosts/month",
        "monthly_tokens": 10000,
        "giveaway_entries": "+5",
        "discounts": "15% in Server Rewards & Promotion",
        "role": "@Simple Customer",
        "description": "Standard VRT pass",
        "vrt_price": 0  # Can't be bought with VRT
    },
    "Big Pass": {
        "price": "$7.99/month",
        "monthly_tokens": 18000,
        "giveaway_entries": "+8",
        "discounts": "15% in Server Rewards & Promotion, 10% in Discord/PayPal/Brawl Stars",
        "role": "@Big Customer",
        "description": "Great value pass",
        "vrt_price": 0  # Can't be bought with VRT
    },
    "Ultra Pass": {
        "price": "$10.99/month",
        "monthly_tokens": 25000,
        "giveaway_entries": "+12",
        "discounts": "15% on everything",
        "role": "@Ultra Customer",
        "description": "Premium pass with all benefits",
        "vrt_price": 0  # Can't be bought with VRT
    },
    "Ultimate Pass": {
        "price": "$19.99/month",
        "monthly_tokens": 45000,
        "giveaway_entries": "+15",
        "discounts": "20% on everything",
        "role": "@I am rich.",
        "description": "The ultimate pass (not recommended)",
        "vrt_price": 0  # Can't be bought with VRT
    }
}

# Shop View
class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.current_category = "PayPal Rewards"
        self.showing_items = True
        self.current_page = 0
        self.items_per_page = 5
    
    def create_items_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = discord.Embed(
            title="🎁 VRT Shop - Items",
            description="Purchase items with your VRT tokens using `/buy [item name]`",
            color=discord.Color.blue()
        )
        
        category_items = {k: v for k, v in SHOP_ITEMS.items() if v["category"] == self.current_category}
        items = list(category_items.items())
        
        if not items:
            embed.add_field(
                name="No items in this category",
                value="Please select another category",
                inline=False
            )
        else:
            start_idx = self.current_page * self.items_per_page
            end_idx = start_idx + self.items_per_page
            paginated_items = items[start_idx:end_idx]
            
            for item_name, item_data in paginated_items:
                embed.add_field(
                    name=f"🔹 {item_name} - {item_data['price']:,} VRT",
                    value=item_data["description"],
                    inline=False
                )
            
            embed.set_footer(text=f"Page {self.current_page + 1}/{(len(items) + self.items_per_page - 1) // self.items_per_page} | Category: {self.current_category}")
        
        return embed
    
    def create_passes_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎫 VRT Shop - Passes",
            description="VRT Passes provide monthly benefits and discounts",
            color=discord.Color.gold()
        )
        
        for pass_name, pass_data in VRT_PASSES.items():
            embed.add_field(
                name=f"🌟 {pass_name} - {pass_data['price']}",
                value=(
                    f"📦 **Monthly Tokens:** {pass_data['monthly_tokens']:,} VRT\n"
                    f"🎟️ **Giveaway Entries:** {pass_data['giveaway_entries']}\n"
                    f"💎 **Discounts:** {pass_data['discounts']}\n"
                    f"👑 **Role:** {pass_data['role']}\n"
                    f"*{pass_data['description']}*"
                ),
                inline=False
            )
        
        embed.set_footer(text="Passes cannot be purchased with VRT tokens - contact staff for purchase")
        return embed
    
    @discord.ui.select(
        placeholder="Select a category...",
        options=[
            discord.SelectOption(label="PayPal Rewards", description="PayPal credit rewards", emoji="💳"),
            discord.SelectOption(label="Brawl Stars Rewards", description="Brawl Stars items", emoji="🎮"),
            discord.SelectOption(label="Discord Rewards", description="Discord Nitro and more", emoji="🤖"),
            discord.SelectOption(label="Promoting", description="Promotion options", emoji="📢"),
            discord.SelectOption(label="Server Roles", description="Permanent server roles", emoji="👑"),
            discord.SelectOption(label="Custom Roles", description="Customize your role", emoji="🎨"),
            discord.SelectOption(label="Stickers/Emojis", description="Add stickers/emojis", emoji="😀"),
            discord.SelectOption(label="Giveaway Entries", description="Extra giveaway entries", emoji="🎟️"),
        ],
        row=0
    )
    async def select_category(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.current_category = select.values[0]
        self.current_page = 0
        if self.showing_items:
            embed = self.create_items_embed(interaction)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="🛒 Items", style=discord.ButtonStyle.primary, row=1)
    async def show_items(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.showing_items = True
        self.current_page = 0
        embed = self.create_items_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🎫 Passes", style=discord.ButtonStyle.secondary, row=1)
    async def show_passes(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.showing_items = False
        embed = self.create_passes_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.grey, row=2)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.showing_items:
            category_items = {k: v for k, v in SHOP_ITEMS.items() if v["category"] == self.current_category}
            max_pages = (len(category_items) + self.items_per_page - 1) // self.items_per_page
            self.current_page = (self.current_page - 1) % max_pages
            embed = self.create_items_embed(interaction)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.grey, row=2)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.showing_items:
            category_items = {k: v for k, v in SHOP_ITEMS.items() if v["category"] == self.current_category}
            max_pages = (len(category_items) + self.items_per_page - 1) // self.items_per_page
            self.current_page = (self.current_page + 1) % max_pages
            embed = self.create_items_embed(interaction)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()

# Bot events
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print('------')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Process commands
    await bot.process_commands(message)

    # Count words (5 words = 1 point)
    word_count = len(message.content.split())
    points_to_add = word_count // 5
    
    if points_to_add > 0:
        await db.add_points(message.author.id, points_to_add)

        # Check if points reach threshold for tokens
        points = await db.get_points(message.author.id)
        if points >= 150:
            tokens_to_add = random.randint(60, 75)
            user_data = await db.get_user(message.author.id)
            await db.update_user(message.author.id, {
                "tokens": user_data.get("tokens", 0) + tokens_to_add,
                "points": 0  # Reset points after conversion
            })
            await db.record_transaction(message.author.id, tokens_to_add, "Weekly points conversion")
            
            # Notify user
            try:
                embed = discord.Embed(
                    title="🎉 Points Converted to VRT Tokens!",
                    description=f"You've earned {tokens_to_add} VRT tokens from your message points!",
                    color=discord.Color.green()
                )
                embed.add_field(name="New Balance", value=f"{user_data.get('tokens', 0) + tokens_to_add} VRT")
                await message.author.send(embed=embed)
            except discord.Forbidden:
                pass  # User has DMs disabled

# Commands
@bot.tree.command(name="balance", description="Check your VRT token and points balance")
async def balance(interaction: discord.Interaction):
    user_data = await db.get_user(interaction.user.id)
    if not user_data:
        user_data = await db.create_user(interaction.user.id)
    
    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s Balance",
        color=discord.Color.blurple()
    )
    embed.add_field(name="VRT Tokens", value=f"{user_data.get('tokens', 0):,}", inline=True)
    embed.add_field(name="Points", value=f"{user_data.get('points', 0):,}", inline=True)
    embed.add_field(name="Total Words", value=f"{user_data.get('total_words', 0):,}", inline=False)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="shop", description="Browse the VRT shop items and passes")
async def shop(interaction: discord.Interaction):
    view = ShopView()
    embed = view.create_items_embed(interaction)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="buy", description="Purchase an item from the VRT shop")
@app_commands.describe(item="The item you want to purchase")
async def buy(interaction: discord.Interaction, item: str):
    if item not in SHOP_ITEMS:
        await interaction.response.send_message("❌ That item doesn't exist in the shop!", ephemeral=True)
        return
    
    user_data = await db.get_user(interaction.user.id)
    if not user_data:
        user_data = await db.create_user(interaction.user.id)
    
    item_data = SHOP_ITEMS[item]
    
    if user_data.get("tokens", 0) < item_data["price"]:
        await interaction.response.send_message(
            f"❌ You don't have enough VRT tokens for this purchase!\n"
            f"You need {item_data['price']:,} VRT but only have {user_data.get('tokens', 0):,} VRT.",
            ephemeral=True
        )
        return
    
    # Process purchase
    new_balance = user_data["tokens"] - item_data["price"]
    await db.update_user(interaction.user.id, {"tokens": new_balance})
    await db.record_transaction(interaction.user.id, -item_data["price"], f"Purchased {item}")
    await db.record_purchase(interaction.user.id, item, item_data["price"])

    # Send confirmation DM
    embed = discord.Embed(
        title="✅ Purchase Successful!",
        description=f"Thank you for purchasing **{item}**!",
        color=discord.Color.green()
    )
    embed.add_field(name="Item Price", value=f"{item_data['price']:,} VRT", inline=True)
    embed.add_field(name="New Balance", value=f"{new_balance:,} VRT", inline=True)
    embed.add_field(
        name="Next Steps", 
        value="Please open a ticket in our server to claim your prize.", 
        inline=False
    )
    
    try:
        await interaction.user.send(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message(
            "I couldn't send you a DM! Please enable DMs from server members to receive purchase details.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "Purchase successful! Check your DMs for details.",
            ephemeral=True
        )

    # Log purchase
    log_channel_id = os.getenv("LOG_CHANNEL_ID")
    if log_channel_id:
        log_channel = bot.get_channel(int(log_channel_id))
        if log_channel:
            log_embed = discord.Embed(
                title="🛒 New Purchase",
                description=f"**User:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                            f"**Item:** {item}\n"
                            f"**Price:** {item_data['price']:,} VRT",
                color=discord.Color.orange()
            )
            log_embed.set_thumbnail(url=interaction.user.display_avatar.url)
            await log_channel.send(content="<@&MOD_ROLE_ID>", embed=log_embed)

@bot.tree.command(name="transactions", description="View your recent VRT token transactions")
@app_commands.describe(limit="Number of transactions to show (max 10)")
async def transactions(interaction: discord.Interaction, limit: int = 5):
    limit = min(max(limit, 1), 10)  # Clamp between 1 and 10
    data = db._read_data(db.transactions_file)
    user_transactions = data.get(str(interaction.user.id), [])[-limit:][::-1]  # Get latest transactions
    
    if not user_transactions:
        await interaction.response.send_message("You don't have any transactions yet.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"Your Recent Transactions (Last {len(user_transactions)})",
        color=discord.Color.blurple()
    )
    
    for tx in user_transactions:
        amount = tx["amount"]
        embed.add_field(
            name=f"{'+' if amount > 0 else ''}{amount:,} VRT - {tx['reason']}",
            value=f"<t:{int(datetime.fromisoformat(tx['timestamp']).timestamp())}:R>\n"
                  f"Balance: {tx['balance']:,} VRT",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Run the bot
if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
