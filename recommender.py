import os
import psycopg2
import psycopg2.extras
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

def main():
    # Load environment variables
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("Error: DATABASE_URL not found in .env file.")
        return

    print("Connecting to database...")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # 1. Create table if it doesn't exist
        print("Ensuring book_recommendations table exists...")
        create_table_query = """
        CREATE TABLE IF NOT EXISTS book_recommendations (
            book_id INTEGER PRIMARY KEY REFERENCES books(book_id) ON DELETE CASCADE,
            recommended_ids INTEGER[]
        );
        """
        cur.execute(create_table_query)
        conn.commit()

        # 2. Fetch data
        print("Fetching books data...")
        cur.execute("SELECT book_id, title, author, description FROM books;")
        books_data = cur.fetchall()
        
        if not books_data:
            print("No books found in the database.")
            return
            
        # Create DataFrame
        df = pd.DataFrame(books_data, columns=['book_id', 'title', 'author', 'description'])
        print(f"Loaded {len(df)} books.")
        
        # 3. Preprocess data
        print("Preprocessing data...")
        # Fill missing values with empty string
        df.fillna('', inplace=True)
        
        # Combine text fields for TF-IDF
        df['combined_features'] = df['title'] + " " + df['author'] + " " + df['description']
        
        # 4. Calculate similarities
        print("Calculating TF-IDF and Cosine Similarity...")
        tfidf = TfidfVectorizer(stop_words='english')
        tfidf_matrix = tfidf.fit_transform(df['combined_features'])
        
        cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)
        
        # 5. Extract top 5 recommendations for each book
        print("Generating top 5 recommendations per book...")
        recommendations = []
        
        for idx in range(len(df)):
            book_id = int(df.iloc[idx]['book_id'])
            
            # Get similarity scores for the current book
            sim_scores = list(enumerate(cosine_sim[idx]))
            
            # Sort the books based on the similarity scores (descending)
            sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
            
            # Get the scores of the 5 most similar books (ignoring the first one, which is the book itself)
            top_5_scores = sim_scores[1:6]
            
            # Get the book indices
            book_indices = [i[0] for i in top_5_scores]
            
            # Map indices back to book_id
            recommended_ids = df.iloc[book_indices]['book_id'].astype(int).tolist()
            
            recommendations.append((book_id, recommended_ids))
            
        # 6. Upsert into database
        print("Upserting recommendations into database...")
        upsert_query = """
        INSERT INTO book_recommendations (book_id, recommended_ids)
        VALUES %s
        ON CONFLICT (book_id) 
        DO UPDATE SET recommended_ids = EXCLUDED.recommended_ids;
        """
        
        psycopg2.extras.execute_values(
            cur,
            upsert_query,
            recommendations,
            template=None,
            page_size=100
        )
        
        conn.commit()
        print("Successfully updated book recommendations!")
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.rollback()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        print("Database connection closed.")

if __name__ == "__main__":
    main()
