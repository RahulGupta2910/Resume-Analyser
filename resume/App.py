import streamlit as st
import pandas as pd
import base64
import random
import time
import datetime
import os
import json
import pymysql
from pyresparser import ResumeParser
from pdfminer3.layout import LAParams
from pdfminer3.pdfpage import PDFPage
from pdfminer3.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer3.converter import TextConverter
import io
from streamlit_tags import st_tags
from PIL import Image
import plotly.express as px
import nltk
import spacy
from yt_dlp import YoutubeDL

# Download required NLP packages once
nltk.download('stopwords')
nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')
nltk.download('wordnet')
nltk.download('maxent_ne_chunker')
nltk.download('words')
spacy.cli.download("en_core_web_sm")

# Import your course lists (make sure Courses.py exists and is correct)
from Courses import ds_course, web_course, android_course, ios_course, uiux_course, resume_videos, interview_videos

# --- Helper Functions ---

def fetch_yt_video_title(link):
    ydl_opts = {'quiet': True}
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(link, download=False)
        return info_dict.get('title', None)

def get_table_download_link(df, filename, text):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'
    return href

def pdf_reader(file):
    resource_manager = PDFResourceManager()
    fake_file_handle = io.StringIO()
    converter = TextConverter(resource_manager, fake_file_handle, laparams=LAParams())
    page_interpreter = PDFPageInterpreter(resource_manager, converter)
    with open(file, 'rb') as fh:
        for page in PDFPage.get_pages(fh, caching=True, check_extractable=True):
            page_interpreter.process_page(page)
        text = fake_file_handle.getvalue()
    converter.close()
    fake_file_handle.close()
    return text

def show_pdf(file_path):
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def course_recommender(course_list):
    st.subheader("**Courses & Certificates Recommendations 🎓**")
    rec_course = []
    no_of_reco = st.slider('Choose Number of Course Recommendations:', 1, 10, 5)
    random.shuffle(course_list)
    for idx, (c_name, c_link) in enumerate(course_list):
        if idx == no_of_reco:
            break
        st.markdown(f"({idx+1}) [{c_name}]({c_link})")
        rec_course.append(c_name)
    return rec_course

# --- Database Connection ---

connection = pymysql.connect(host='localhost', user='root', password='@Maruti800', db='cv')
cursor = connection.cursor()

def insert_data(name, email, res_score, timestamp, no_of_pages, reco_field, cand_level, skills, recommended_skills, courses):
    DB_table_name = 'user_data'
    insert_sql = f"""INSERT INTO {DB_table_name} 
                     (Name, Email_ID, resume_score, Timestamp, Page_no, Predicted_Field, User_level, Actual_skills, Recommended_skills, Recommended_courses)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
    # Convert lists to JSON strings before inserting
    rec_values = (
        name,
        email,
        str(res_score),
        timestamp,
        str(no_of_pages),
        reco_field,
        cand_level,
        json.dumps(skills),
        json.dumps(recommended_skills),
        json.dumps(courses),
    )
    cursor.execute(insert_sql, rec_values)
    connection.commit()

# --- Data Decoding Helpers for Admin ---

def decode_text_column(col):
    def safe_decode(x):
        if isinstance(x, bytes):
            try:
                return x.decode('utf-8')
            except:
                return x
        return x
    return col.apply(safe_decode)

def decode_json_column(col):
    def safe_parse(x):
        if isinstance(x, bytes):
            x = x.decode('utf-8')
        try:
            return json.loads(x)
        except Exception:
            return x
    return col.apply(safe_parse)

# --- Streamlit App ---

st.set_page_config(
    page_title="AI Resume Analyzer",
    page_icon='./Logo/logo2.png',
)

def run():
    # Show logo - update path as needed

    dark_mode = st.toggle("🌙 Dark Mode")

    if dark_mode:
        st.markdown(
            """
            <style>
            body {
                background-color: #0e1117;
                color: white;
            }
            .stApp {
                background-color: #0e1117;
                color: white;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <style>
            body {
                background-color: white;
                color: black;
            }
            .stApp {
                background-color: white;
                color: black;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

    try:
        img = Image.open('c:/Users/grahu/Desktop/My Codes/resume/logo/logo2.png')
        st.image(img)
    except Exception as e:
        st.write("Logo not found or failed to load.")

    st.title("AI Resume Analyser")

    st.sidebar.markdown("# Choose User")
    activities = ["User", "Admin"]
    choice = st.sidebar.selectbox("Choose among the given options:", activities)

    link = '[©Developed by Rahul Gupta](https://www.linkedin.com/in/rahul-gupta-29oct/)'
    st.sidebar.markdown(link, unsafe_allow_html=True)

    # Create DB and Table if not exist
    cursor.execute("CREATE DATABASE IF NOT EXISTS CV;")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_data (
            ID INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            Name VARCHAR(500) NOT NULL,
            Email_ID VARCHAR(500) NOT NULL,
            resume_score VARCHAR(8) NOT NULL,
            Timestamp VARCHAR(50) NOT NULL,
            Page_no VARCHAR(5) NOT NULL,
            Predicted_Field VARCHAR(100) NOT NULL,
            User_level VARCHAR(100) NOT NULL,
            Actual_skills TEXT NOT NULL,
            Recommended_skills TEXT NOT NULL,
            Recommended_courses TEXT NOT NULL
        );
        """
    )

    if choice == 'User':
        st.markdown(
            '''<h5 style='text-align: left; color: #021659;'>Upload your resume, and get smart recommendations</h5>''',
            unsafe_allow_html=True,
        )
        pdf_file = st.file_uploader("Choose your Resume", type=["pdf"])
        if pdf_file is not None:
            with st.spinner('Uploading your Resume...'):
                time.sleep(3)
            save_path = './Uploaded_Resumes/' + pdf_file.name
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(pdf_file.getbuffer())
            show_pdf(save_path)

            # Extract resume data using pyresparser
            resume_data = ResumeParser(save_path).get_extracted_data()
            if resume_data:
                resume_text = pdf_reader(save_path)

                st.header("**Resume Analysis**")
                st.success("Hello " + resume_data.get('name', 'Candidate'))

                st.subheader("**Your Basic Info**")
                try:
                    st.text('Name: ' + resume_data.get('name', 'N/A'))
                    st.text('Email: ' + resume_data.get('email', 'N/A'))
                    st.text('Contact: ' + resume_data.get('mobile_number', 'N/A'))
                    st.text('Resume pages: ' + str(resume_data.get('no_of_pages', 'N/A')))
                except Exception:
                    pass

                cand_level = ''
                pages = resume_data.get('no_of_pages', 1)
                if pages == 1:
                    cand_level = "Fresher"
                    st.markdown('''<h4 style='color: #d73b5c;'>You are at Fresher level!</h4>''', unsafe_allow_html=True)
                elif pages == 2:
                    cand_level = "Intermediate"
                    st.markdown('''<h4 style='color: #1ed760;'>You are at Intermediate level!</h4>''', unsafe_allow_html=True)
                elif pages >= 3:
                    cand_level = "Experienced"
                    st.markdown('''<h4 style='color: #fba171;'>You are at Experienced level!</h4>''', unsafe_allow_html=True)

                # Skills recommendations based on keywords
                keywords = st_tags(
                    label='### Your Current Skills',
                    text='See our skills recommendation below',
                    value=resume_data.get('skills', []),
                    key='1',
                )

                ds_keywords = [
                    'tensorflow', 'keras', 'pytorch', 'machine learning', 'deep learning', 'flask', 'streamlit'
                ]
                web_keywords = [
                    'react', 'django', 'node js', 'react js', 'php', 'laravel', 'magento', 'wordpress',
                    'javascript', 'angular js', 'c#', 'flask'
                ]
                android_keywords = ['android', 'android development', 'flutter', 'kotlin', 'xml', 'kivy']
                ios_keywords = ['ios', 'ios development', 'swift', 'cocoa', 'cocoa touch', 'xcode']
                uiux_keywords = [
                    'ux', 'adobe xd', 'figma', 'zeplin', 'balsamiq', 'ui', 'prototyping', 'wireframes', 'storyframes',
                    'adobe photoshop', 'photoshop', 'editing', 'adobe illustrator', 'illustrator', 'adobe after effects',
                    'after effects', 'adobe premier pro', 'premier pro', 'adobe indesign', 'indesign', 'wireframe', 'solid',
                    'grasp', 'user research', 'user experience'
                ]

                recommended_skills = []
                reco_field = ''
                rec_course = []

                skills_lower = [skill.lower() for skill in resume_data.get('skills', [])]

                # Recommend courses & skills based on skill keywords
                def recommend(field_keywords, field_name, rec_skills, course_list, key):
                    nonlocal reco_field, recommended_skills, rec_course
                    if any(kw in skills_lower for kw in field_keywords):
                        reco_field = field_name
                        st.success(f"** Our analysis says you are looking for {field_name} Jobs.**")
                        recommended_skills = rec_skills
                        st_tags(label='### Recommended skills for you.',
                                text='Recommended skills generated from System',
                                value=recommended_skills,
                                key=key)
                        st.markdown(
                            '''<h4 style='color: #1ed760;'>Adding these skills to resume will boost 🚀 the chances of getting a Job 💼</h4>''',
                            unsafe_allow_html=True)
                        rec_course = course_recommender(course_list)
                        return True
                    return False

                if not recommend(ds_keywords, 'Data Science',
                                 ['Data Visualization', 'Predictive Analysis', 'Statistical Modeling', 'Data Mining',
                                  'Clustering & Classification', 'Data Analytics', 'Quantitative Analysis', 'Web Scraping',
                                  'ML Algorithms', 'Keras', 'Pytorch', 'Probability', 'Scikit-learn', 'Tensorflow',
                                  'Flask', 'Streamlit'],
                                 ds_course, '2'):
                    if not recommend(web_keywords, 'Web Development',
                                     ['React', 'Django', 'Node JS', 'React JS', 'PHP', 'Laravel', 'Magento', 'WordPress',
                                      'JavaScript', 'Angular JS', 'C#', 'Flask', 'SDK'],
                                     web_course, '3'):
                        if not recommend(android_keywords, 'Android Development',
                                         ['Android', 'Android Development', 'Flutter', 'Kotlin', 'XML', 'Java', 'Kivy', 'GIT',
                                          'SDK', 'SQLite'],
                                         android_course, '4'):
                            if not recommend(ios_keywords, 'IOS Development',
                                             ['IOS', 'IOS Development', 'Swift', 'Cocoa', 'Cocoa Touch', 'Xcode',
                                              'Objective-C', 'SQLite', 'Plist', 'StoreKit', 'UI-Kit', 'AV Foundation',
                                              'Auto-Layout'],
                                             ios_course, '5'):
                                if not recommend(uiux_keywords, 'UI-UX Development',
                                                 ['UI', 'User Experience', 'Adobe XD', 'Figma', 'Zeplin', 'Balsamiq',
                                                  'Prototyping', 'Wireframes', 'Storyframes', 'Adobe Photoshop',
                                                  'Editing', 'Illustrator', 'After Effects', 'Premier Pro', 'Indesign',
                                                  'Wireframe', 'Solid', 'Grasp', 'User Research'],
                                                 uiux_course, '6'):
                                    st.info("No matching skill category found for recommendations.")

                # Timestamp for DB entry
                ts = time.time()
                cur_date = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                cur_time = datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S')
                timestamp = f"{cur_date}_{cur_time}"

                # Resume writing tips & scoring
                st.subheader("**Resume Tips & Ideas 💡**")
                resume_score = 0

                if 'Objective' in resume_text:
                    resume_score += 20
                    st.markdown('''<h5 style='color: #1ed760;'>[+] Awesome! You have added Objective</h5>''', unsafe_allow_html=True)
                else:
                    st.markdown('''<h5>Please add your career objective for better recruiter understanding.</h5>''', unsafe_allow_html=True)

                if 'Declaration' in resume_text:
                    resume_score += 20
                    st.markdown('''<h5 style='color: #1ed760;'>[+] Awesome! You have added Declaration</h5>''', unsafe_allow_html=True)
                else:
                    st.markdown('''<h5>Please add Declaration for authenticity assurance.</h5>''', unsafe_allow_html=True)

                if ('Hobbies' in resume_text) or ('Interests' in resume_text):
                    resume_score += 20
                    st.markdown('''<h5 style='color: #1ed760;'>[+] Awesome! You have added Hobbies/Interests</h5>''', unsafe_allow_html=True)
                else:
                    st.markdown('''<h5>Please add Hobbies/Interests to showcase your personality.</h5>''', unsafe_allow_html=True)

                if 'Achievements' in resume_text:
                    resume_score += 20
                    st.markdown('''<h5 style='color: #1ed760;'>[+] Awesome! You have added Achievements</h5>''', unsafe_allow_html=True)
                else:
                    st.markdown('''<h5>Please add Achievements to show your capabilities.</h5>''', unsafe_allow_html=True)

                if 'Projects' in resume_text:
                    resume_score += 20
                    st.markdown('''<h5 style='color: #1ed760;'>[+] Awesome! You have added Projects</h5>''', unsafe_allow_html=True)
                else:
                    st.markdown('''<h5>Please add Projects to demonstrate your experience.</h5>''', unsafe_allow_html=True)

                # Show Resume Score progress bar
                st.subheader("**Resume Score 📝**")
                my_bar = st.progress(0)
                for percent_complete in range(resume_score):
                    time.sleep(0.05)
                    my_bar.progress(percent_complete + 1)
                st.success(f"** Your Resume Writing Score: {resume_score} **")
                st.warning("** Note: This score is based on content present in your Resume. **")
                st.balloons()

                # Insert user data into database
                insert_data(
                    resume_data.get('name', ''),
                    resume_data.get('email', ''),
                    resume_score,
                    timestamp,
                    pages,
                    reco_field,
                    cand_level,
                    resume_data.get('skills', []),
                    recommended_skills,
                    rec_course,
                )

                # Bonus videos for resume writing and interview tips
                st.header("**Bonus Video for Resume Writing Tips 💡**")
                resume_vid = random.choice(resume_videos)
                st.subheader("✅ **" + fetch_yt_video_title(resume_vid) + "**")
                st.video(resume_vid)

                st.header("**Bonus Video for Interview Tips 💡**")
                interview_vid = random.choice(interview_videos)
                st.subheader("✅ **" + fetch_yt_video_title(interview_vid) + "**")
                st.video(interview_vid)

            else:
                st.error('Failed to extract resume data. Please try another resume.')

    else:
        # --- Admin Section ---
        st.success('Welcome to Admin Side')
        ad_user = st.text_input("Username")
        ad_password = st.text_input("Password", type='password')
        query = "SELECT * FROM user_data"

        # Establish MySQL connection for admin separately to avoid conflicts
        connection_admin = pymysql.connect(host='localhost', user='root', password='@Maruti800', db='cv')
        cursor_admin = connection_admin.cursor()

        if st.button('Login'):
            if ad_user == 'rahul' and ad_password == 'rahulgupta':
                # Fetch data into pandas DataFrame
                plot_data = pd.read_sql(query, connection_admin)

                # Decode columns with text or JSON
                plot_data['Predicted_Field'] = decode_text_column(plot_data['Predicted_Field'])
                plot_data['User_level'] = decode_text_column(plot_data['User_level'])

                plot_data['Actual_skills'] = decode_json_column(plot_data['Actual_skills'])
                plot_data['Recommended_skills'] = decode_json_column(plot_data['Recommended_skills'])
                plot_data['Recommended_courses'] = decode_json_column(plot_data['Recommended_courses'])

                # Pie Chart: Predicted Field
                counts = plot_data['Predicted_Field'].value_counts().reset_index()
                counts.columns = ['Predicted_Field', 'Count']
                st.subheader("**Pie Chart for Predicted Field Recommendation**")
                fig = px.pie(counts, values='Count', names='Predicted_Field', title='Predicted Field according to the Skills')
                st.plotly_chart(fig)

                # Pie Chart: User Level
                counts_level = plot_data['User_level'].value_counts().reset_index()
                counts_level.columns = ['User_level', 'Count']
                st.subheader("**Pie Chart for User's Experienced Level**")
                fig_level = px.pie(counts_level, values='Count', names='User_level', title="User's Experienced Level")
                st.plotly_chart(fig_level)

                # Display Data Table
                st.subheader("**User Data Table**")

                # Convert list columns to comma-separated string for display
                plot_data['Actual_skills'] = plot_data['Actual_skills'].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)
                plot_data['Recommended_skills'] = plot_data['Recommended_skills'].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)
                plot_data['Recommended_courses'] = plot_data['Recommended_courses'].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)

                st.dataframe(plot_data)

                # Download link for CSV export
                st.markdown(get_table_download_link(plot_data, "user_data.csv", "Download data as CSV"), unsafe_allow_html=True)

            else:
                st.error('Incorrect username or password!')

if __name__ == "__main__":
    run()
