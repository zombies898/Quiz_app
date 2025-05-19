import streamlit as st
import pandas as pd
import numpy as np
import base64
import json
import time
import sqlite3
import os
import random
from datetime import datetime

# Set page configuration
st.set_page_config(
    page_title="Mobile Quiz App",
    page_icon="❓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better mobile experience
st.markdown("""
<style>
    .main-container {
        max-width: 100%;
        padding: 1rem;
    }
    
    /* Card styling for questions */
    .question-card {
        background-color: #FFFFFF;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
    }
    
    /* Button styling */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        padding: 10px 20px;
        width: 100%;
        transition: all 0.3s ease;
    }
    
    /* Primary action button */
    .primary-button button {
        background-color: #4CAF50;
        color: white;
    }
    
    /* Secondary action button */
    .secondary-button button {
        background-color: #2196F3;
        color: white;
    }
    
    /* Answer options */
    .answer-option {
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 10px;
        cursor: pointer;
        transition: background-color 0.3s ease;
    }
    
    /* Correct answer highlight */
    .correct-answer {
        background-color: rgba(76, 175, 80, 0.2);
        border: 1px solid #4CAF50;
    }
    
    /* Incorrect answer highlight */
    .incorrect-answer {
        background-color: rgba(244, 67, 54, 0.2);
        border: 1px solid #F44336;
    }
    
    /* Results section */
    .results-section {
        text-align: center;
        padding: 20px;
    }
    
    .score-display {
        font-size: 24px;
        font-weight: bold;
        color: #212121;
        margin: 20px 0;
    }
</style>
""", unsafe_allow_html=True)

# Database setup - Using SQLite for mobile compatibility
DB_PATH = "quiz_data.db"

def init_db():
    """Initialize SQLite database with necessary tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create quizzes table
    c.execute('''
    CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create questions table
    c.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        options TEXT NOT NULL,
        correct_answer TEXT NOT NULL,
        position INTEGER NOT NULL,
        FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
    )
    ''')
    
    # Create attempts table for scores
    c.execute('''
    CREATE TABLE IF NOT EXISTS quiz_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER NOT NULL,
        user_name TEXT,
        score REAL NOT NULL,
        max_score INTEGER NOT NULL,
        percentage REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Database helper functions
def create_quiz_from_csv(title, description, quiz_data):
    """Save quiz data to the SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        # Insert quiz record
        c.execute(
            "INSERT INTO quizzes (title, description) VALUES (?, ?)",
            (title, description)
        )
        quiz_id = c.lastrowid
        
        # Insert question records
        for i, question_data in enumerate(quiz_data):
            options_json = json.dumps(question_data['options'])
            c.execute(
                "INSERT INTO questions (quiz_id, question_text, options, correct_answer, position) VALUES (?, ?, ?, ?, ?)",
                (quiz_id, question_data['question'], options_json, question_data['answer'], i+1)
            )
        
        conn.commit()
        return quiz_id
    except Exception as e:
        conn.rollback()
        st.error(f"Database error: {str(e)}")
        return None
    finally:
        conn.close()

def get_all_quizzes():
    """Retrieve all quizzes from the database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT id, title, description, created_at FROM quizzes ORDER BY created_at DESC")
    quizzes = c.fetchall()
    
    result = []
    for quiz in quizzes:
        result.append({
            'id': quiz[0],
            'title': quiz[1],
            'description': quiz[2],
            'created_at': quiz[3]
        })
    
    conn.close()
    return result

def get_quiz_by_id(quiz_id):
    """Retrieve a specific quiz and its questions"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get quiz
    c.execute("SELECT id, title, description FROM quizzes WHERE id = ?", (quiz_id,))
    quiz = c.fetchone()
    
    if not quiz:
        conn.close()
        return None, []
    
    # Get questions
    c.execute("SELECT question_text, options, correct_answer FROM questions WHERE quiz_id = ? ORDER BY position", (quiz_id,))
    questions = c.fetchall()
    
    processed_questions = []
    for q in questions:
        try:
            options_list = json.loads(q[1])
        except (json.JSONDecodeError, TypeError):
            options_list = []
            
        processed_questions.append({
            'question': q[0],
            'options': options_list,
            'answer': q[2]
        })
    
    quiz_data = {
        'id': quiz[0],
        'title': quiz[1],
        'description': quiz[2]
    }
    
    conn.close()
    return quiz_data, processed_questions

def save_quiz_attempt(quiz_id, user_name, score, max_score):
    """Save a completed quiz attempt"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    percentage = (score / max_score) * 100 if max_score > 0 else 0
    
    try:
        c.execute(
            "INSERT INTO quiz_attempts (quiz_id, user_name, score, max_score, percentage) VALUES (?, ?, ?, ?, ?)",
            (quiz_id, user_name, score, max_score, percentage)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Error saving score: {str(e)}")
        return False
    finally:
        conn.close()

def get_quiz_leaderboard(quiz_id, limit=10):
    """Get top scores for a quiz"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute(
        "SELECT user_name, score, max_score, percentage FROM quiz_attempts WHERE quiz_id = ? ORDER BY score DESC LIMIT ?", 
        (quiz_id, limit)
    )
    attempts = c.fetchall()
    
    result = []
    for attempt in attempts:
        result.append({
            'user_name': attempt[0] if attempt[0] else "Anonymous",
            'score': attempt[1],
            'max_score': attempt[2],
            'percentage': attempt[3]
        })
    
    conn.close()
    return result

# CSV processing functions
def validate_csv(file):
    """
    Validates if the uploaded file is a proper CSV with required columns for quiz generation.
    Supports two formats:
    1. 'question', 'options', 'answer' - where options is a comma-separated string
    2. 'question', 'option1', 'option2', ... 'optionN', 'answer' - where options are in separate columns
    """
    try:
        # Read CSV file
        content = file.read()
        data = pd.read_csv(pd.io.common.BytesIO(content))
        
        # Validate data structure
        if data.empty:
            return False, "CSV file is empty."
        
        # Determine the CSV format
        has_options_column = 'options' in data.columns
        has_option_columns = any(col.startswith('option') for col in data.columns)
        
        # Check required columns based on format
        if has_options_column:
            # Format 1: 'question', 'options', 'answer'
            required_columns = ['question', 'options', 'answer']
            missing_columns = [col for col in required_columns if col not in data.columns]
            
            if missing_columns:
                return False, f"Missing required columns: {', '.join(missing_columns)}"
            
            # Process data for format 1
            processed_data = []
            for i in range(len(data)):
                row = data.iloc[i]
                
                # Convert to string to ensure compatibility
                question = str(row['question'])
                options_str = str(row['options'])
                answer_str = str(row['answer'])
                
                if ',' not in options_str:
                    return False, f"Row {i+1}: 'options' must be a comma-separated string of choices"
                
                options = [opt.strip() for opt in options_str.split(',')]
                if len(options) < 2:
                    return False, f"Row {i+1}: At least 2 options are required"
                
                if answer_str.strip() not in options:
                    return False, f"Row {i+1}: Answer '{answer_str}' is not in the options list"
                
                processed_data.append({
                    'question': question,
                    'options': options,
                    'answer': answer_str.strip()
                })
            
        elif has_option_columns:
            # Format 2: 'question', 'option1', 'option2', etc., 'answer'
            required_columns = ['question', 'answer']
            option_columns = [col for col in data.columns if col.startswith('option')]
            
            if not option_columns:
                return False, "No option columns found. Required format: 'question', 'option1', 'option2', ..., 'answer'"
            
            if 'question' not in data.columns or 'answer' not in data.columns:
                missing = []
                if 'question' not in data.columns:
                    missing.append('question')
                if 'answer' not in data.columns:
                    missing.append('answer')
                return False, f"Missing required columns: {', '.join(missing)}"
            
            # Process data for format 2
            processed_data = []
            for i in range(len(data)):
                row = data.iloc[i]
                
                # Get question and convert to string
                question = str(row['question'])
                
                # Collect options, ensuring they're strings and not null
                options = []
                for col in option_columns:
                    if col in row.index and pd.notna(row[col]):
                        options.append(str(row[col]))
                
                if len(options) < 2:
                    return False, f"Row {i+1}: At least 2 options are required"
                
                # Handle the answer
                answer = str(row['answer'])
                
                # Check if answer is a number (index to option)
                if answer.isdigit():
                    answer_idx = int(answer) - 1  # Convert to 0-based index
                    if 0 <= answer_idx < len(options):
                        answer = options[answer_idx]
                    else:
                        return False, f"Row {i+1}: Answer index {answer} is out of range"
                
                # Check if answer matches one of the options
                if answer not in options:
                    # Try case-insensitive matching
                    match_found = False
                    for opt in options:
                        if opt.lower() == answer.lower():
                            answer = opt  # Use the option with correct case
                            match_found = True
                            break
                    
                    if not match_found:
                        return False, f"Row {i+1}: Answer '{answer}' is not in the options list"
                
                processed_data.append({
                    'question': question,
                    'options': options,
                    'answer': answer
                })
        else:
            return False, "Invalid CSV format. Required columns: either 'question', 'options', 'answer' OR 'question', 'option1', 'option2', ..., 'answer'"
        
        return True, processed_data
    
    except pd.errors.ParserError:
        return False, "Invalid CSV format. Please check your file."
    except Exception as e:
        return False, f"Error processing file: {str(e)}"

def get_sample_csv_content():
    """Returns sample CSV content for the expected format"""
    return """question,option1,option2,option3,option4,answer
What is the capital of France?,Paris,London,Berlin,Madrid,Paris
Who wrote Romeo and Juliet?,Charles Dickens,William Shakespeare,Jane Austen,Mark Twain,William Shakespeare
What is the largest planet in our solar system?,Earth,Mars,Jupiter,Venus,Jupiter
What is 2+2?,2,3,4,5,4
What is the chemical symbol for water?,H2O,CO2,O2,N2,H2O"""

def shuffle_quiz_data(quiz_data):
    """Shuffles the quiz data to randomize question order"""
    shuffled_data = quiz_data.copy()
    random.shuffle(shuffled_data)
    return shuffled_data

# Session state initialization and management
def initialize_session_state():
    """Initialize session state variables if they don't exist"""
    if 'quiz_data' not in st.session_state:
        st.session_state.quiz_data = None
    
    if 'current_question' not in st.session_state:
        st.session_state.current_question = 0
    
    if 'score' not in st.session_state:
        st.session_state.score = 0
    
    if 'selected_option' not in st.session_state:
        st.session_state.selected_option = None
    
    if 'submitted' not in st.session_state:
        st.session_state.submitted = False
    
    if 'quiz_completed' not in st.session_state:
        st.session_state.quiz_completed = False

def reset_quiz():
    """Reset the quiz state to start over"""
    st.session_state.quiz_data = None
    st.session_state.current_question = 0
    st.session_state.score = 0
    st.session_state.selected_option = None
    st.session_state.submitted = False
    st.session_state.quiz_completed = False

def select_option(option):
    """Sets the selected option in the session state"""
    st.session_state.selected_option = option
    st.session_state.submitted = False

def submit_answer():
    """Process the submitted answer and update the score"""
    if st.session_state.selected_option is not None:
        st.session_state.submitted = True
        
        current_question = st.session_state.quiz_data[st.session_state.current_question]
        if st.session_state.selected_option == current_question['answer']:
            st.session_state.score += 1

def next_question():
    """Advance to the next question or complete the quiz"""
    if st.session_state.current_question < len(st.session_state.quiz_data) - 1:
        st.session_state.current_question += 1
        st.session_state.selected_option = None
        st.session_state.submitted = False
    else:
        st.session_state.quiz_completed = True

# Initialize session state for tracking app state
initialize_session_state()

# App title and description
st.markdown("<h1 style='text-align: center; color: #4CAF50;'>Mobile Quiz App</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.2em;'>Create and take quizzes on your Android device</p>", unsafe_allow_html=True)

# Sidebar for navigation and options
with st.sidebar:
    st.markdown("## Quiz Menu")
    
    # Get all available quizzes from database
    all_quizzes = get_all_quizzes()
    
    nav_option = st.radio(
        "Choose an option:",
        ["Create New Quiz", "Take Existing Quiz", "View Leaderboards"],
        index=0
    )
    
    if nav_option == "Take Existing Quiz" and all_quizzes:
        quiz_titles = [f"{quiz['title']} (ID: {quiz['id']})" for quiz in all_quizzes]
        selected_quiz = st.selectbox("Select a quiz:", quiz_titles)
        
        if selected_quiz:
            # Extract quiz ID from the selection
            quiz_id = int(selected_quiz.split("(ID: ")[1].split(")")[0])
            
            if st.button("Load Selected Quiz"):
                # Get quiz data from database
                quiz_obj, quiz_questions = get_quiz_by_id(quiz_id)
                
                if quiz_obj and quiz_questions:
                    # Store quiz info in session state
                    st.session_state.quiz_id = quiz_obj['id']
                    st.session_state.quiz_title = quiz_obj['title']
                    
                    # Reset quiz state and load questions
                    reset_quiz()
                    shuffled_data = shuffle_quiz_data(quiz_questions)
                    st.session_state.quiz_data = shuffled_data
                    st.rerun()
                else:
                    st.error("Could not load quiz questions.")
    
    elif nav_option == "View Leaderboards" and all_quizzes:
        quiz_titles = [f"{quiz['title']} (ID: {quiz['id']})" for quiz in all_quizzes]
        leaderboard_quiz = st.selectbox("Select a quiz:", quiz_titles, key="leaderboard_select")
        
        if leaderboard_quiz:
            # Extract quiz ID from the selection
            quiz_id = int(leaderboard_quiz.split("(ID: ")[1].split(")")[0])
            
            # Display leaderboard for selected quiz
            leaderboard = get_quiz_leaderboard(quiz_id)
            
            if leaderboard:
                st.markdown("### Top Scores")
                for i, attempt in enumerate(leaderboard):
                    name = attempt['user_name'] or "Anonymous"
                    st.markdown(f"**{i+1}.** {name}: {attempt['score']}/{attempt['max_score']} ({attempt['percentage']:.1f}%)")
            else:
                st.info("No attempts recorded for this quiz yet.")
    
    # Reset option
    if st.button("Reset Quiz"):
        reset_quiz()
        st.rerun()

# Main content division
if not st.session_state.quiz_data:
    if nav_option == "Create New Quiz":
        # File upload section
        st.markdown("<div style='padding: 20px; border: 2px dashed #2196F3; border-radius: 10px;'>", unsafe_allow_html=True)
        st.subheader("Create a New Quiz")
        
        # Quiz metadata
        quiz_title = st.text_input("Quiz Title", "My Quiz")
        quiz_description = st.text_area("Quiz Description (Optional)", "A collection of questions to test your knowledge.")
        
        # Instructions for CSV format
        with st.expander("CSV Format Instructions"):
            st.markdown("""
            ### Required CSV Format
            Your CSV file can have either of these formats:
            
            #### Format 1:
            - **question**: The question text
            - **options**: Comma-separated list of choices (e.g., "Paris,London,Berlin,Madrid")
            - **answer**: The correct answer (must exactly match one of the options)
            
            #### Format 2:
            - **question**: The question text
            - **option1, option2, option3, ...**: Individual columns for each option
            - **answer**: The correct answer (must exactly match one of the options)
            
            ### Sample CSV Format:
            """)
            st.code(get_sample_csv_content(), language="text")
            
            # Download sample CSV button
            sample_csv = get_sample_csv_content()
            b64 = base64.b64encode(sample_csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="sample_quiz.csv">Download Sample CSV</a>'
            st.markdown(href, unsafe_allow_html=True)
        
        # File uploader
        uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])
        
        if uploaded_file is not None:
            is_valid, result = validate_csv(uploaded_file)
            
            if is_valid:
                st.success("CSV file validated successfully!")
                
                # Save quiz to database button
                if st.button("Create Quiz"):
                    with st.spinner("Saving quiz..."):
                        try:
                            # Save quiz to database
                            quiz_id = create_quiz_from_csv(quiz_title, quiz_description, result)
                            
                            if quiz_id:
                                st.session_state.quiz_id = quiz_id
                                st.session_state.quiz_title = quiz_title
                                
                                # Shuffle the questions
                                shuffled_data = shuffle_quiz_data(result)
                                st.session_state.quiz_data = shuffled_data
                                
                                st.success(f"Quiz saved! Quiz ID: {quiz_id}")
                                time.sleep(1)  # Brief pause to show the success message
                                st.rerun()
                            else:
                                st.error("Failed to save quiz to database.")
                        except Exception as e:
                            st.error(f"Error saving quiz: {str(e)}")
            else:
                st.error(f"Error in CSV file: {result}")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif nav_option == "Take Existing Quiz":
        if all_quizzes:
            st.info("Select a quiz from the sidebar menu to begin.")
        else:
            st.warning("No quizzes available. Create a quiz first!")
    
    elif nav_option == "View Leaderboards":
        if all_quizzes:
            st.info("Select a quiz from the sidebar menu to view its leaderboard.")
        else:
            st.warning("No quizzes available to show leaderboards.")

else:
    # Quiz in progress
    if not st.session_state.quiz_completed:
        # Show quiz title if available
        if hasattr(st.session_state, 'quiz_title'):
            st.subheader(f"Quiz: {st.session_state.quiz_title}")
        
        # Progress bar
        progress = (st.session_state.current_question + 1) / len(st.session_state.quiz_data)
        st.progress(progress)
        st.write(f"Question {st.session_state.current_question + 1} of {len(st.session_state.quiz_data)}")
        
        # Current question display
        current_q = st.session_state.quiz_data[st.session_state.current_question]
        
        # Question card
        st.markdown("<div class='question-card'>", unsafe_allow_html=True)
        st.subheader(current_q['question'])
        
        # Options list
        for option in current_q['options']:
            option_class = ""
            if st.session_state.submitted:
                if option == current_q['answer']:
                    option_class = "correct-answer"
                elif option == st.session_state.selected_option and option != current_q['answer']:
                    option_class = "incorrect-answer"
            
            # Create a button-like clickable area for each option
            if st.button(
                option, 
                key=f"option_{option}", 
                disabled=st.session_state.submitted,
                help="Click to select this answer"
            ):
                select_option(option)
            
            # Apply styling based on selection state
            if st.session_state.selected_option == option and not st.session_state.submitted:
                st.markdown(f"<div class='answer-option' style='background-color: rgba(33, 150, 243, 0.2); border: 1px solid #2196F3;'>Selected: {option}</div>", unsafe_allow_html=True)
            elif option_class:
                st.markdown(f"<div class='answer-option {option_class}'>{option}</div>", unsafe_allow_html=True)
                
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Control buttons row
        col1, col2 = st.columns(2)
        
        with col1:
            submit_button = st.button(
                "Submit Answer", 
                key="submit",
                disabled=st.session_state.selected_option is None or st.session_state.submitted,
                help="Submit your selected answer"
            )
            if submit_button:
                submit_answer()
                st.rerun()
        
        with col2:
            next_button = st.button(
                "Next Question", 
                key="next",
                disabled=not st.session_state.submitted,
                help="Go to the next question"
            )
            if next_button:
                next_question()
                st.rerun()
                
        # Feedback after submission
        if st.session_state.submitted:
            if st.session_state.selected_option == current_q['answer']:
                st.success("Correct! Well done.")
            else:
                st.error(f"Incorrect. The correct answer is: {current_q['answer']}")
    
    else:
        # Quiz completed - show results
        st.markdown("<div class='results-section'>", unsafe_allow_html=True)
        st.subheader("Quiz Completed!")
        
        # Calculate and display score
        total_questions = len(st.session_state.quiz_data)
        correct_answers = st.session_state.score
        percentage = (correct_answers / total_questions) * 100
        
        st.markdown(f"<div class='score-display'>Your Score: {correct_answers}/{total_questions} ({percentage:.1f}%)</div>", unsafe_allow_html=True)
        
        # Performance feedback
        if percentage >= 80:
            st.balloons()
            st.success("Excellent job! You've mastered this quiz!")
        elif percentage >= 60:
            st.success("Good work! You're on the right track!")
        else:
            st.info("Keep practicing! You'll improve with time.")
        
        # Save score to leaderboard
        if hasattr(st.session_state, 'quiz_id'):
            st.subheader("Save Your Score")
            user_name = st.text_input("Your Name (Optional)", "")
            
            if st.button("Save Score to Leaderboard"):
                with st.spinner("Saving score..."):
                    result = save_quiz_attempt(
                        st.session_state.quiz_id,
                        user_name,
                        correct_answers,
                        total_questions
                    )
                    if result:
                        st.success("Score saved to leaderboard!")
                    else:
                        st.error("Could not save score.")
        
        # Reset quiz button
        if st.button("Take Another Quiz", key="reset"):
            reset_quiz()
            st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.markdown("""
<div style='text-align: center; margin-top: 30px; padding: 10px; color: #757575; font-size: 0.8em;'>
    Mobile Quiz App - Create and take quizzes on your Android device
</div>
""", unsafe_allow_html=True)