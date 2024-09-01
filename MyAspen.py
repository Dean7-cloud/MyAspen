import json
from datetime import datetime, timedelta
import os
import shutil
from colorama import Fore, Style, init
from pushbullet import Pushbullet
from flask import Flask, request, jsonify
import hashlib
import smtplib
from email.mime.text import MIMEText
import time	
from email.mime.multipart import MIMEMultipart

init(autoreset=True)

DATA_FILE = "balance_data.json"
PB_API_KEY = "PB_API_KEY"  # Replace with your Pushbullet API key

pb = Pushbullet(PB_API_KEY)


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as file:
            return json.load(file)
    else:
        return None

def save_data(data):
    with open(DATA_FILE, "w") as file:
        json.dump(data, file)

def onboarding():
    print(f"{Fore.YELLOW}👋 Welcome to the ASPEN Card Balance Tracker Setup!")
    try:
        current_balance = float(input("Enter your current balance(Note that the amount should be exact): £"))
        weekly_amount = float(input("Enter the weekly amount you receive(note that the amount should be exact): £"))
       
        notify_choice = input("Do you want to be notified each day you receive a new balance? (yes/no, press Enter to skip): ").strip().lower()

      
        if notify_choice == 'yes':
            configure_notifications()
        
        data = {
            "weekly_amount": weekly_amount,
            "current_balance": current_balance,
            "last_renewal_date": "",  # No renewal has happened yet
            "transactions": [],
            "first_run": False
        }

        save_data(data)
        print(f"{Fore.GREEN}✔ Setup complete! Your current balance is set to £{current_balance} and weekly amount to £{weekly_amount}.")
        return data
    except ValueError:
        print(f"{Fore.RED}❌ Invalid input. Please enter valid numbers.")
        return onboarding()

def configure_notifications():
    while true:
          print(f"{Fore.YELLOW}📢 Notification Configuration 📢")
          print(f"{Fore.CYAN}1. Pushbullet(Please make sure you have an API key ready)")
          print(f"{Fore.CYAN}2. Email(You have to verify your email)")
          print(f"{Fore.YELLOW}3.Back to Set Up")

          choice = input(f"{Fore.WHITE}Choose an option (1-3):").strip()

          if choice == "1":
              configure_pushbullet()
              break
          elif choice == "2":
             configure_email()
             break
          elif choice == "3":
               break
          else:
             print(f"{Fore.RED} ❌ Invalid choice. Please choose a valid option. ")

def configure_pushbullet():
    print(f"{Fore.YELLOW}Configuring Pushbullet Notifications")
    pushbullet_api_key = input("Enter your Pushbullet API key: ").strip()

    # Save the API key
    with open("config.py", "w") as file:
        file.write(f'PB_API_KEY = "{pushbullet_api_key}"\n')

    print(f"{Fore.GREEN}✔ Pushbullet notifications configured successfully!")


def send_verification_email(email):
    verification_token = hashlib.sha256(email.encode()).hexdigest()
    verification_link = f"https://yourserver-ip:5000/verify?email={email}&token{verification_token}"


    msg = MIMEText(f"Please verify your email by clicking on the following link:  {verification_link}")
    msg['subject'] = "Email Verification"
    msg['From'] = "your-email@example.com"
    msg['To'] = email

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
             server.starttls()
             server.login("your-email@example.com", "your-email-password")
             server.send_message(msg)
        print(f"{Fore.GREEN}✅ Verification email sent to {email}. Please check your inbox.")
    except Exception as e:
        print(f"{Fore.RED}❌ Failed to send verification email: {e}")

def check_verification_status(email):
    print(f"{Fore.YELLOW}⌛ Waiting for email verification...")
    while True:
        response = requests.get(f"http://your-server-ip:5000/verify_status?email={email}")
        if response.status_code == 200 and response.json().get("status") == "verified":
            print(f"{Fore.GREEN}✔ Email verified successfully!")
            return True
        time.sleep(5)  # Poll every 5 seconds

def configure_email():
    email = input("Enter your email address: ").strip()
    send_verification_email(email)
    if check_verification_status(email):
        print(f"{Fore.GREEN}✔ Email configuration complete! You will now receive notifications via email.")
    else:
        print(f"{Fore.RED}❌ Email verification failed. Please try again.")


def send_notification(title, message, email=None):
    try:
        # Pushbullet notification
        if not email:
            pb.push_note(title, message)
        
        # Email notification
        else:
            send_email_notification(title, message, email)
    except Exception as e:
        print(f"{Fore.RED}❌ Failed to send notification: {e}")

def send_email_notification(subject, message, recipient_email):
    sender_email = "email@example.com"  # Replace with your email
    sender_password = "password"  # Replace with your email password

    # Creating the email content
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    # Attach the message body to the email
    msg.attach(MIMEText(message, 'plain'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()  # Start TLS for security
            server.login(sender_email, sender_password)  # Login to the SMTP server
            server.sendmail(sender_email, recipient_email, msg.as_string())  # Send the email
        print(f"{Fore.GREEN}✔ Email sent to {recipient_email}")
    except Exception as e:
        print(f"{Fore.RED}❌ Failed to send email: {e}")

# Function to update the balance on Monday, accounting for missed weeks
def update_balance(data):
    today = datetime.now().date()
    last_renewal = datetime.strptime(data["last_renewal_date"], "%Y-%m-%d").date() if data["last_renewal_date"] else None

    if not last_renewal:
        print(f"{Fore.MAGENTA}🗓 No updates until the next Monday.")
        return

    days_since_last_renewal = (today - last_renewal).days
    missed_weeks = days_since_last_renewal // 7

    if missed_weeks > 0:
        added_amount = data["weekly_amount"] * missed_weeks
        data["current_balance"] += added_amount
        data["last_renewal_date"] = (last_renewal + timedelta(weeks=missed_weeks)).strftime("%Y-%m-%d")
        save_data(data)
        print(f"{Fore.GREEN}🗓 Balance updated: +£{added_amount} added for {missed_weeks} missed week(s).")
        
        # Send Pushbullet or Email notification
        if 'email' in data:
            send_notification(
                "A$PEN Card Balance Update",
                f"Your balance has been updated by £{added_amount}. New balance: £{data['current_balance']}",
                email=data['email']
            )
        else:
            send_notification(
                "A$PEN Card Balance Update",
                f"Your balance has been updated by £{added_amount}. New balance: £{data['current_balance']}"
            )
    
    elif today.weekday() == 0 and last_renewal != today:
        data["current_balance"] += data["weekly_amount"]
        data["last_renewal_date"] = today.strftime("%Y-%m-%d")
        save_data(data)
        print(f"{Fore.GREEN}🗓 Balance updated: +£{data['weekly_amount']} added.")
        
        # Send Pushbullet or Email notification
        if 'email' in data:
            send_notification(
                "A$PEN Card Balance Update",
                f"Your balance has been updated by £{data['weekly_amount']}. New balance: £{data['current_balance']}",
                email=data['email']
            )
        else:
            send_notification(
                "A$PEN Card Balance Update",
                f"Your balance has been updated by £{data['weekly_amount']}. New balance: £{data['current_balance']}"
            )


# Function to set or edit the weekly amount
def set_weekly_amount(data):
    try:
        amount = float(input("Enter the weekly amount you receive: £"))
        data["weekly_amount"] = amount
        save_data(data)
        print(f"{Fore.YELLOW}✔ Weekly amount set to £{amount}.")
    except ValueError:
        print(f"{Fore.RED}❌ Invalid input. Please enter a valid number.")

# Function to add a transaction (deduct spending)
def add_transaction(data):
    try:
        spent = float(input("Enter the amount you spent: £"))
        if spent > data["current_balance"]:
            print(f"{Fore.RED}❌ Insufficient balance!")
        else:
            data["current_balance"] -= spent
            data["transactions"].append({
                "type": "Spending",
                "amount": spent,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_data(data)
            print(f"{Fore.RED}📉 £{spent} deducted from your balance.")
    except ValueError:
        print(f"{Fore.RED}❌ Invalid input. Please enter a valid number.")

# Function to deposit an amount
def deposit(data):
    try:
        amount = float(input("Enter the amount to deposit: £"))
        data["current_balance"] += amount
        data["transactions"].append({
            "type": "Deposit",
            "amount": amount,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_data(data)
        print(f"{Fore.GREEN}💰 £{amount} deposited into your balance.")
    except ValueError:
        print(f"{Fore.RED}❌ Invalid input. Please enter a valid number.")

# Function to withdraw an amount
def withdraw(data):
    try:
        amount = float(input("Enter the amount to withdraw: £"))
        if amount > data["current_balance"]:
            print(f"{Fore.RED}❌ Insufficient balance!")
        else:
            data["current_balance"] -= amount
            data["transactions"].append({
                "type": "Withdrawal",
                "amount": amount,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_data(data)
            print(f"{Fore.BLUE}🏧 £{amount} withdrawn from your balance.")
    except ValueError:
        print(f"{Fore.RED}❌ Invalid input. Please enter a valid number.")

# Function to check current balance
def check_balance(data):
    print(f"{Fore.CYAN}💳 Current Balance: £{data['current_balance']}")

# Function to view transaction history
def view_history(data):
    if data["transactions"]:
        print(f"{Fore.CYAN}📜 Transaction History:")
        for i, transaction in enumerate(data["transactions"], 1):
            print(f"{i}. {transaction['type']} - £{transaction['amount']} on {transaction['date']}")
    else:
        print(f"{Fore.YELLOW}📝 No transactions recorded yet.")

# Submenu for Deposit and Withdraw
def deposit_withdraw_menu(data):
    while True:
        print(f"\n{Fore.YELLOW}🏦 Deposit & Withdrawal 🏦")
        print(f"{Fore.CYAN}1. Deposit Money")
        print(f"{Fore.CYAN}2. Withdraw Money")
        print(f"{Fore.YELLOW}3. Back to Main Menu")

        choice = input(f"{Fore.WHITE}Choose an option (1-3): ")

        if choice == "1":
            deposit(data)
        elif choice == "2":
            withdraw(data)
        elif choice == "3":
            break
        else:
            print(f"{Fore.RED}❌ Invalid choice. Please choose a valid option.")

# Function to clear the terminal and center the output
def clear_and_center_output():
    os.system('cls' if os.name == 'nt' else 'clear')  # Clear the terminal screen
    columns, _ = shutil.get_terminal_size()
    return columns

# Main function
def main():
    data = load_data()

    # If data is None, run the onboarding process
    if data is None:
        data = onboarding()

    update_balance(data)

    while True:
        # Clear the terminal and get the terminal width
        terminal_width = clear_and_center_output()

        # Center the ASCII art and menu in the terminal
        header = [
            f"{Fore.GREEN}   █████╗   ██████╗ ██████╗ ███████╗███╗   ██╗",
            f"{Fore.GREEN}  ██╔══██╗ ██╔════╝ ██╔══██╗██╔════╝████╗  ██║",
            f"{Fore.GREEN}  ███████║ ╚█████╗  ██████╔╝█████╗  ██╔██╗ ██║",
            f"{Fore.GREEN}  ██╔══██║  ╚═══██╗ ██╔═══╝ ██╔══╝  ██║╚██╗██║",
            f"{Fore.GREEN}  ██║  ██║ ██████╔╝ ██║     ███████╗██║ ╚████║",
            f"{Fore.GREEN}  ╚═╝  ╚═╝ ╚═════╝  ╚═╝     ╚══════╝╚═╝  ╚═══╝",
        ]


        menu = [
            f"{Fore.YELLOW}💸 ASPEN Card Balance Tracker 💸",
            f"{Fore.CYAN}1. Set/Change Weekly Amount",
            f"{Fore.CYAN}2. Add Spending",
            f"{Fore.CYAN}3. Deposit & Withdrawal",
            f"{Fore.CYAN}4. View Transaction History",
            f"{Fore.YELLOW}5. Exit",
        ]

        # Print the centered header and menu with spacing
        for line in header:
            print(line.center(terminal_width))

        print("\n" * 2)  # Add extra spacing between ASCII art and menu

        for line in menu:
            print(line.center(terminal_width))

        # Always display current balance at the bottom, centered
        balance_line = f"{Fore.GREEN}💳 Current Balance: £{data['current_balance']}"
        print(f"\n{balance_line.center(terminal_width)}\n")

        choice = input(f"{Fore.YELLOW}Choose an option (1-5): ")

        if choice == "1":
            set_weekly_amount(data)
        elif choice == "2":
            add_transaction(data)
        elif choice == "3":
            deposit_withdraw_menu(data)
        elif choice == "4":
            view_history(data)
        elif choice == "5":
            print(f"{Fore.YELLOW}👋 Goodbye!")
            break
        else:
            print(f"{Fore.RED}❌ Invalid choice. Please choose a valid option.")

if __name__ == "__main__":
    main()
