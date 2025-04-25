import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import random
import asyncio
import os
from dotenv import load_dotenv

# Load token from .env file
load_dotenv()

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
bot = commands.Bot(command_prefix="%")

# Channel ID for the Open Ticket button
TICKET_CHANNEL_ID = 000011111  # Replace with your actual channel ID
STAFF_ROLE_NAME = 'Ticket Staff'  # Replace with your actual staff role name
TICKET_CATEGORY_ID = 1234567890  # Replace with the category ID you want tickets to be created in

# Create ticket button embed
@bot.command()
async def setup_ticket(ctx):
    channel = bot.get_channel(TICKET_CHANNEL_ID)
    button = Button(label="Open Ticket", style=discord.ButtonStyle.green)

    async def button_callback(interaction):
        # Show the ticket modal form when clicked
        modal = TicketModal()
        await interaction.response.send_modal(modal)

    button.callback = button_callback

    view = View()
    view.add_item(button)

    embed = discord.Embed(
        title="Create a Ticket",
        description="Click the button below to open a ticket and get assistance.",
        color=discord.Color.green()
    )

    await channel.send(embed=embed, view=view)

# Modal to collect ticket information
class TicketModal(Modal):
    def __init__(self):
        super().__init__(title="Open Ticket")

        self.team_name = TextInput(label="What is your team name?", required=True)
        self.issue = TextInput(label="What is the issue?", required=True)
        self.proof = TextInput(label="Provide proof (if any, or say 'Sent screenshot')", required=False)

        self.add_item(self.team_name)
        self.add_item(self.issue)
        self.add_item(self.proof)

    async def callback(self, interaction: discord.Interaction):
        # Create private ticket channel
        team_name = self.team_name.value
        issue = self.issue.value
        proof = self.proof.value

        category = discord.utils.get(interaction.guild.categories, id=TICKET_CATEGORY_ID)
        ticket_channel = await interaction.guild.create_text_channel(
            f"{team_name}-{random.randint(1000, 9999)}", category=category
        )

        # Rename ticket to the team name
        await ticket_channel.set_permissions(interaction.guild.default_role, read_messages=False)
        staff_role = discord.utils.get(interaction.guild.roles, name=STAFF_ROLE_NAME)
        await ticket_channel.set_permissions(staff_role, read_messages=True)

        # Send embed with ticket info
        embed = discord.Embed(
            title=f"Ticket for {team_name}",
            description=f"**Issue**: {issue}\n**Proof**: {proof if proof else 'No proof provided'}",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Ticket opened by {interaction.user}")
        await ticket_channel.send(embed=embed)

        # Respond to the user
        await interaction.response.send_message(f"Your ticket has been created! Please provide your screenshot in {ticket_channel.mention}.", ephemeral=True)

        # Add a close button when staff responds
        await self.add_close_button(ticket_channel)

    async def add_close_button(self, ticket_channel):
        # Close button for staff
        close_button = Button(label="Close Ticket", style=discord.ButtonStyle.red)

        async def close_callback(interaction):
            # When the close button is clicked, close the ticket
            await ticket_channel.delete()
            await interaction.response.send_message("Ticket closed.", ephemeral=True)

        close_button.callback = close_callback

        view = View()
        view.add_item(close_button)
        await ticket_channel.send("Ticket is now being processed.", view=view)

# Command to setup the ticket system
@bot.command()
async def setup(ctx):
    await setup_ticket(ctx)

# Running the bot using token from .env
bot.run(os.getenv("TOKEN"))
