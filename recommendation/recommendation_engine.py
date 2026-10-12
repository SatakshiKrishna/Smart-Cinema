# recommendation/recommendation_engine.py

import os
import sys

import pandas as pd
import mysql.connector

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Find the main SmartCinema project folder
project_root = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

# Add the project folder to Python's import path
# This allows this file to import config.py
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from config import DB_CONFIG


# Loads movie information from MySQL
def load_movie_data():

    connection = mysql.connector.connect(
        **DB_CONFIG
    )

    query = """
        SELECT
            m.movie_id,
            m.title,
            m.description,
            m.language,
            m.age_rating,
            m.status,

            GROUP_CONCAT(
                DISTINCT g.genre_name
                SEPARATOR ' '
            ) AS genres

        FROM movies m

        LEFT JOIN movie_genres mg
            ON m.movie_id = mg.movie_id

        LEFT JOIN genres g
            ON mg.genre_id = g.genre_id

        GROUP BY
            m.movie_id,
            m.title,
            m.description,
            m.language,
            m.age_rating,
            m.status

        ORDER BY m.movie_id;
    """

    # Convert SQL query result into a Pandas DataFrame
    movies = pd.read_sql(
        query,
        connection
    )

    connection.close()

    # Replace NULL values so ML text processing does not fail
    movies["description"] = (
        movies["description"].fillna("")
    )

    movies["language"] = (
        movies["language"].fillna("")
    )

    movies["age_rating"] = (
        movies["age_rating"].fillna("")
    )

    movies["genres"] = (
        movies["genres"].fillna("")
    )

    movies["status"] = (
        movies["status"].fillna("")
    )

    return movies


# Combines movie fields into one text feature
def prepare_movie_features(movies):

    # Work on a copy of the DataFrame
    movies = movies.copy()

    movies["combined_features"] = (
        movies["genres"]
        + " "
        + movies["language"]
        + " "
        + movies["age_rating"]
        + " "
        + movies["description"]
    )

    # Lowercase text gives more consistent comparisons
    movies["combined_features"] = (
        movies["combined_features"]
        .str.lower()
    )

    return movies


# Builds TF-IDF vectors and cosine similarity
def build_similarity_matrix(movies):

    # TF-IDF converts text into numerical vectors
    tfidf = TfidfVectorizer(
        stop_words="english"
    )

    tfidf_matrix = tfidf.fit_transform(
        movies["combined_features"]
    )

    # Compare each movie with every other movie
    similarity_matrix = cosine_similarity(
        tfidf_matrix,
        tfidf_matrix
    )

    return similarity_matrix


# Finds movies similar to one selected movie
def recommend_movies(movie_id, limit=5):

    movies = load_movie_data()

    # At least two movies are needed
    if len(movies) < 2:
        return []

    movies = prepare_movie_features(
        movies
    )

    similarity_matrix = build_similarity_matrix(
        movies
    )

    # Find the row containing the selected movie
    movie_matches = movies.index[
        movies["movie_id"] == movie_id
    ].tolist()

    if not movie_matches:
        return []

    movie_index = movie_matches[0]

    # Get similarity values for this movie
    similarity_scores = list(
        enumerate(
            similarity_matrix[movie_index]
        )
    )

    # Highest score should come first
    similarity_scores = sorted(
        similarity_scores,
        key=lambda item: item[1],
        reverse=True
    )

    recommendations = []

    for index, score in similarity_scores:

        # Do not recommend the selected movie itself
        if index == movie_index:
            continue

        movie = movies.iloc[index]

        recommendations.append(
            {
                "movie_id": int(
                    movie["movie_id"]
                ),
                "title": movie["title"],
                "language": movie["language"],
                "genres": movie["genres"],
                "status": movie["status"],
                "similarity_score": round(
                    float(score),
                    3
                )
            }
        )

        # Stop after requested number of movies
        if len(recommendations) >= limit:
            break

    return recommendations


# Creates recommendations based on a customer's history
def recommend_for_user(user_id, limit=5):

    movies = load_movie_data()

    if len(movies) < 2:
        return []

    movies = prepare_movie_features(
        movies
    )

    similarity_matrix = build_similarity_matrix(
        movies
    )

    connection = mysql.connector.connect(
        **DB_CONFIG
    )

    cursor = connection.cursor(
        dictionary=True
    )

    # Find movies that the customer has successfully booked
    cursor.execute("""
        SELECT DISTINCT
            sh.movie_id

        FROM bookings b

        JOIN shows sh
            ON b.show_id = sh.show_id

        WHERE b.user_id = %s
        AND b.booking_status = 'confirmed'
    """, (
        user_id,
    ))

    booked_movies = cursor.fetchall()

    # Find movie ratings submitted by the customer
    cursor.execute("""
        SELECT
            movie_id,
            rating

        FROM reviews

        WHERE user_id = %s
    """, (
        user_id,
    ))

    reviewed_movies = cursor.fetchall()

    cursor.close()
    connection.close()

    # Movies already watched or reviewed should not
    # normally appear as recommendations again
    watched_movie_ids = set()

    # Each movie from the user's history receives a weight
    preference_movies = []

    # Confirmed bookings give us basic preference information
    for booking in booked_movies:

        movie_id = booking["movie_id"]

        watched_movie_ids.add(
            movie_id
        )

        preference_movies.append(
            {
                "movie_id": movie_id,
                "weight": 1.0
            }
        )

    # Ratings provide stronger preference information
    for review in reviewed_movies:

        movie_id = review["movie_id"]
        rating = review["rating"]

        watched_movie_ids.add(
            movie_id
        )

        # High ratings should influence recommendations more
        if rating >= 4:
            weight = 2.0

        elif rating == 3:
            weight = 1.0

        else:
            weight = 0.3

        preference_movies.append(
            {
                "movie_id": movie_id,
                "weight": weight
            }
        )

    # New users may not have enough history yet
    if not preference_movies:
        return []

    recommendation_scores = {}

    # Compare every preference movie with all other movies
    for preference in preference_movies:

        preferred_movie_id = preference[
            "movie_id"
        ]

        weight = preference[
            "weight"
        ]

        movie_matches = movies.index[
            movies["movie_id"]
            == preferred_movie_id
        ].tolist()

        if not movie_matches:
            continue

        preferred_index = movie_matches[0]

        for index, similarity in enumerate(
            similarity_matrix[
                preferred_index
            ]
        ):

            candidate_movie = movies.iloc[
                index
            ]

            candidate_id = int(
                candidate_movie["movie_id"]
            )

            # Do not recommend something already watched/reviewed
            if candidate_id in watched_movie_ids:
                continue

            # Only recommend movies currently available
            if candidate_movie["status"] != "now_showing":
                continue

            weighted_score = (
                float(similarity)
                * weight
            )

            if candidate_id not in recommendation_scores:
                recommendation_scores[
                    candidate_id
                ] = 0

            recommendation_scores[
                candidate_id
            ] += weighted_score

    # Highest personalized score comes first
    sorted_recommendations = sorted(
        recommendation_scores.items(),
        key=lambda item: item[1],
        reverse=True
    )

    recommendations = []

    for movie_id, score in sorted_recommendations:

        movie_match = movies[
            movies["movie_id"] == movie_id
        ]

        if movie_match.empty:
            continue

        movie = movie_match.iloc[0]

        recommendations.append(
            {
                "movie_id": int(
                    movie["movie_id"]
                ),
                "title": movie["title"],
                "language": movie["language"],
                "genres": movie["genres"],
                "status": movie["status"],
                "similarity_score": round(
                    float(score),
                    3
                )
            }
        )

        if len(recommendations) >= limit:
            break

    return recommendations


# Used only when testing this file directly
if __name__ == "__main__":

    movie_data = load_movie_data()

    print("\nMovie Data:\n")

    print(movie_data)

    if len(movie_data) > 0:

        test_movie_id = int(
            movie_data.iloc[0][
                "movie_id"
            ]
        )

        print(
            "\nSimilar movies for movie ID:",
            test_movie_id
        )

        results = recommend_movies(
            test_movie_id,
            limit=5
        )

        if results:

            for movie in results:

                print(
                    f"- {movie['title']} "
                    f"| Genres: {movie['genres']} "
                    f"| Score: {movie['similarity_score']}"
                )

        else:

            print(
                "No recommendations available."
            )