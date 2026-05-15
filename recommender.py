import os
import psycopg2
import psycopg2.extras
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv


def main():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("Error: DATABASE_URL not found in .env file.")
        return

    print("Connecting to database...")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # 1. Tạo bảng nếu chưa có
        print("Ensuring book_recommendations table exists...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS book_recommendations (
                book_id INTEGER PRIMARY KEY REFERENCES books(book_id) ON DELETE CASCADE,
                recommended_ids INTEGER[]
            );
        """)
        conn.commit()

        # 2. Lấy dữ liệu - 1 đại diện duy nhất mỗi ISBN (tránh trùng tựa sách)
        print("Fetching unique books by ISBN...")
        cur.execute("""
            SELECT DISTINCT ON (isbn)
                book_id, isbn, title, author, description
            FROM books
            ORDER BY isbn, book_id ASC;
        """)
        rows = cur.fetchall()

        if not rows:
            print("No books found in the database.")
            return

        df = pd.DataFrame(rows, columns=['book_id', 'isbn', 'title', 'author', 'description'])
        print(f"Loaded {len(df)} unique ISBNs.")

        # 3. Xử lý văn bản - kết hợp title + author + description để TF-IDF
        df.fillna('', inplace=True)
        df['combined'] = (
            df['title'].str.lower() + " " +
            df['author'].str.lower() + " " +
            df['description'].str.lower()
        )

        # 4. Tính TF-IDF và Cosine Similarity
        print("Calculating TF-IDF and Cosine Similarity...")
        tfidf = TfidfVectorizer(
            stop_words='english',
            ngram_range=(1, 2),   # Bắt bigram để hiểu ngữ cảnh tốt hơn
            max_features=10000
        )
        tfidf_matrix = tfidf.fit_transform(df['combined'])
        cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

        # 5. Tạo map isbn -> book_id đại diện
        isbn_to_rep_id = dict(zip(df['isbn'], df['book_id']))

        # 6. Sinh top 5 gợi ý KHÁC ISBN cho mỗi cuốn sách đại diện
        print("Generating top 5 unique-ISBN recommendations per book...")
        recs_for_representative = {}  # isbn -> [book_id gợi ý]

        for idx, row in df.iterrows():
            current_isbn = row['isbn']
            sim_scores = list(enumerate(cosine_sim[idx]))
            # Sắp xếp giảm dần, bỏ qua chính nó (score=1.0 với chính nó)
            sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

            top_ids = []
            seen_isbns = {current_isbn}  # Loại trừ ISBN hiện tại
            for other_idx, score in sim_scores:
                if score <= 0:  # Không liên quan chút nào thì bỏ
                    break
                candidate_isbn = df.iloc[other_idx]['isbn']
                if candidate_isbn not in seen_isbns:
                    seen_isbns.add(candidate_isbn)
                    top_ids.append(int(df.iloc[other_idx]['book_id']))
                if len(top_ids) >= 5:
                    break

            recs_for_representative[current_isbn] = top_ids

        # 7. Mở rộng: áp dụng gợi ý cho TẤT CẢ bản sao (cùng ISBN) trong bảng books
        print("Fetching all book_ids from database to apply recommendations...")
        cur.execute("SELECT book_id, isbn FROM books;")
        all_books = cur.fetchall()

        recommendations = []
        for book_id, isbn in all_books:
            rec_ids = recs_for_representative.get(isbn, [])
            if rec_ids:
                recommendations.append((int(book_id), rec_ids))

        # 8. Upsert vào database
        print(f"Upserting {len(recommendations)} book recommendation rows...")
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
            page_size=200
        )

        conn.commit()
        print(f"Done! Updated recommendations for {len(recommendations)} books.")

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.rollback()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        print("Database connection closed.")


if __name__ == "__main__":
    main()
