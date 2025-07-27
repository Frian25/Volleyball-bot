from telegram import Update
from telegram.ext import CallbackContext

def help_command(update: Update, context: CallbackContext):
    help_text = """
🏐 *Volleyball Rating Bot Commands*

/generate_teams YYYY-MM-DD [num_teams]  
→ Generate balanced teams for the specified date  
Example: `/generate_teams 2025-07-28 2`

/result Team1 score1 - score2 Team2  
→ Submit match result  
Example: `/result Red 21 - 18 Blue`

/appeal  
→ Create daily MVP voting (group chat only)  
→ Anonymous polls for each team, 1 hour duration  
→ bonus rating points per match if player gets 66%+ votes

/delete  
→ Delete the last match of today (admin/group only)

/stats PlayerName  
→ Show player's rating, K-factor, matches played  
Example: `/stats John Smith`

/leaderboard  
→ Show top 10 players by rating

/help  
→ Show this help message

📊 *Rating System*:
• Starting rating: 1500  
• Dynamic K-factor (adapts based on matches played)  
• Score margin affects rating changes  
• Ratings decay for inactive players  
• Only active players in match get updated

🏆 *Appeal System*:
• One appeal per day allowed
• Anonymous voting for each team (1 hour)
• Minimum 6 votes required for validation
• 66%+ consensus needed for bonus
• bonus points per match played today
"""
    update.message.reply_text(help_text, parse_mode="Markdown")