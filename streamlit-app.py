import time
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np
import pandas as pd
import simplejson as json
import streamlit as st
from kafka import KafkaConsumer
from streamlit_autorefresh import st_autorefresh
import psycopg2
import geopandas as gpd
import ssl

ssl._create_default_https_context = ssl._create_unverified_context


# Cache the GeoJSON file to avoid re-downloading
@st.cache_data
def load_geojson():
    geojson_url = "https://raw.githubusercontent.com/Subhash9325/GeoJson-Data-of-Indian-States/refs/heads/master/Indian_States"
    return gpd.read_file(geojson_url)


# Function to create a Kafka consumer
def create_kafka_consumer(topic_name):
    # Set up a Kafka consumer with specified topic and configurations
    consumer = KafkaConsumer(
        topic_name,
        bootstrap_servers="localhost:9092",
        auto_offset_reset="earliest",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    )
    return consumer


# Function to fetch voting statistics from PostgreSQL database
@st.cache_data
def fetch_voting_stats():
    # Connect to PostgreSQL database
    conn = psycopg2.connect(
        "host=localhost dbname=voting user=postgres password=postgres"
    )
    cur = conn.cursor()

    # Fetch total number of voters
    cur.execute(
        """
        SELECT count(*) voters_count FROM voters
    """
    )
    voters_count = cur.fetchone()[0]

    # Fetch total number of candidates
    cur.execute(
        """
        SELECT count(*) candidates_count FROM candidates
    """
    )
    candidates_count = cur.fetchone()[0]

    return voters_count, candidates_count


# Function to fetch data from Kafka
def fetch_data_from_kafka(consumer):
    # Poll Kafka consumer for messages within a timeout period
    messages = consumer.poll(timeout_ms=1000)
    data = []

    # Extract data from received messages
    for message in messages.values():
        for sub_message in message:
            data.append(sub_message.value)
    return data


# Function to plot a colored bar chart for vote counts per candidate
def plot_colored_bar_chart(results):
    data_type = results["candidate_name"]
    colors = plt.cm.viridis(np.linspace(0, 1, len(data_type)))
    plt.bar(data_type, results["total_votes"], color=colors)
    plt.xlabel("Candidate")
    plt.ylabel("Total Votes")
    plt.title("Vote Counts per Candidate")
    plt.xticks(rotation=90)
    return plt


# Function to plot a donut chart for vote distribution
def plot_donut_chart(data: pd.DataFrame, title="Donut Chart", type="candidate"):
    if type == "candidate":
        labels = list(data["candidate_name"])
    elif type == "gender":
        labels = list(data["gender"])

    sizes = list(data["total_votes"])
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=140)
    ax.axis("equal")
    plt.title(title)
    return fig


# Function to plot a pie chart for vote distribution
def plot_pie_chart(data, title="Gender Distribution of Voters", labels=None):
    sizes = list(data.values())
    if labels is None:
        labels = list(data.keys())

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=140)
    ax.axis("equal")
    plt.title(title)
    return fig


# Function to split a dataframe into chunks for pagination
@st.cache_data(show_spinner=False)
def split_frame(input_df, rows):
    df = [input_df.loc[i : i + rows - 1, :] for i in range(0, len(input_df), rows)]
    return df


# Function to paginate a table
def paginate_table(table_data):
    # Create columns for the top menu
    top_menu = st.columns(3)

    # Add a unique key for each widget
    with top_menu[0]:
        sort = st.radio(
            "Sort Data",
            options=["Yes", "No"],
            horizontal=1,
            index=1,
            key="sort_data_unique_key",
        )

    if sort == "Yes":
        with top_menu[1]:
            sort_field = st.selectbox(
                "Sort By", options=table_data.columns, key="sort_field_unique_key"
            )
        with top_menu[2]:
            sort_direction = st.radio(
                "Direction",
                options=["⬆️", "⬇️"],
                horizontal=True,
                key="sort_direction_unique_key",
            )
        table_data = table_data.sort_values(
            by=sort_field, ascending=sort_direction == "⬆️", ignore_index=True
        )

    pagination = st.container()

    # Create columns for the bottom menu
    bottom_menu = st.columns((4, 1, 1))

    # Add a unique key for the page size selectbox
    with bottom_menu[2]:
        batch_size = st.selectbox(
            "Page Size", options=[10, 25, 50, 100], key="batch_size_unique_key"
        )

    # Calculate total pages and add a unique key for page number input
    with bottom_menu[1]:
        total_pages = (
            int(len(table_data) / batch_size)
            if int(len(table_data) / batch_size) > 0
            else 1
        )
        current_page = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            step=1,
            key="current_page_unique_key",
        )

    # Remove the key from st.markdown here
    with bottom_menu[0]:
        st.markdown(f"Page **{current_page}** of **{total_pages}** ")

    # Split the dataframe into pages
    pages = split_frame(table_data, batch_size)

    # Display the selected page
    pagination.dataframe(data=pages[current_page - 1], use_container_width=True)


# Function to create and display the static heatmap
def create_static_map(merged_data):
    # Create the figure and axis for the plot
    fig, ax = plt.subplots(figsize=(10, 8))

    # Plot the GeoDataFrame with states and their voter counts
    merged_data.plot(
        column="count",  # Use the 'count' column to color states
        ax=ax,
        cmap="Blues",  # Choose the color map  # Adjust transparency for better aesthetics
        edgecolor="black",  # Add distinct black boundaries
        linewidth=0.1,  # Thin boundary lines
    )

    # Remove axes (latitude/longitude labels)
    ax.axis("off")

    # Add labels for each state
    for _, row in merged_data.iterrows():
        if row["geometry"].centroid:  # Ensure the geometry has a centroid
            centroid = row["geometry"].centroid
            ax.text(
                centroid.x,
                centroid.y,
                row["state"],  # Display state name
                fontsize=5,
                ha="center",
                color="black",
            )

    # Add a title to the map
    ax.set_title("Voter Heatmap by State", fontsize=16, pad=20)

    # Create a colorbar manually using matplotlib
    sm = plt.cm.ScalarMappable(
        cmap="Blues",
        norm=Normalize(
            vmin=merged_data["count"].min(), vmax=merged_data["count"].max()
        ),
    )
    sm.set_array([])

    # Create the colorbar and set label
    cbar = fig.colorbar(sm, ax=ax, orientation="vertical", fraction=0.02)
    cbar.set_label("Voter Count per State", fontsize=12)

    # Format the colorbar ticks to display only integer values
    tick_min = int(merged_data["count"].min())
    tick_max = int(merged_data["count"].max())
    cbar.set_ticks(range(tick_min, tick_max + 1))  # Set integer ticks

    # Tight layout to avoid overlap of elements
    plt.tight_layout()

    return fig


# Function to update data displayed on the dashboard
def update_data():
    # Placeholder to display last refresh time
    last_refresh = st.empty()
    last_refresh.text(f"Last refreshed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Fetch voting statistics (existing logic)
    voters_count, candidates_count = fetch_voting_stats()
    st.markdown("""---""")
    col1, col2 = st.columns(2)
    col1.metric("Total Voters", voters_count)
    col2.metric("Total Candidates", candidates_count)

    # Fetch data from Kafka on aggregated votes per candidate (existing logic)
    consumer = create_kafka_consumer("aggregated_votes_per_candidate")
    data = fetch_data_from_kafka(consumer)
    results = pd.DataFrame(data)

    # Identify the leading candidate (existing logic)
    results = results.loc[results.groupby("candidate_id")["total_votes"].idxmax()]
    leading_candidate = results.loc[results["total_votes"].idxmax()]
    st.markdown("""---""")
    st.header("Leading Candidate")
    col1, col2 = st.columns(2)
    with col1:
        st.image(leading_candidate["photo_url"], width=200)
    with col2:
        st.header(leading_candidate["candidate_name"])
        st.subheader(leading_candidate["party_affiliation"])
        st.subheader("Total Vote: {}".format(leading_candidate["total_votes"]))

    # Display statistics and visualizations (existing logic)
    st.markdown("""---""")
    st.header("Statistics")
    results = results[
        ["candidate_id", "candidate_name", "party_affiliation", "total_votes"]
    ]
    results = results.reset_index(drop=True)
    col1, col2 = st.columns(2)
    with col1:
        bar_fig = plot_colored_bar_chart(results)
        st.pyplot(bar_fig)
    with col2:
        donut_fig = plot_donut_chart(results, title="Vote Distribution")
        st.pyplot(donut_fig)

    # Display table with candidate statistics
    st.table(results)

    # Fetch location-based voting data
    location_consumer = create_kafka_consumer("aggregated_turnout_by_location")
    location_data = fetch_data_from_kafka(location_consumer)
    location_result = pd.DataFrame(location_data)

    # Process the location data (existing logic)
    location_result = location_result.loc[
        location_result.groupby("state")["count"].idxmax()
    ]
    location_result = location_result.reset_index(drop=True)

    # Display location-based voter information (existing logic)
    st.header("Location of Voters")
    paginate_table(location_result)

    # Load the GeoJSON and ensure consistent state names
    india_geojson = load_geojson()
    india_geojson = india_geojson.rename(columns={"NAME_1": "state"})
    india_geojson["state"] = india_geojson["state"].str.title()  # Standardize case

    # Ensure location_result has a consistent state format
    location_result["state"] = location_result["state"].str.title()

    # Merge the updated DataFrame with the cached GeoJSON
    merged = india_geojson.merge(location_result, on="state", how="left").fillna(0)

    # Create the static heatmap
    map_display = create_static_map(merged)

    # Display the static heatmap in Streamlit
    st.title("Voters Across India")
    st.pyplot(map_display)

    # Update the last refresh time
    st.session_state["last_update"] = time.time()


# Sidebar layout
def sidebar():
    # Initialize last update time if not present in session state
    if st.session_state.get("last_update") is None:
        st.session_state["last_update"] = time.time()

    # Slider to control refresh interval
    refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 5, 60, 10)
    st_autorefresh(interval=refresh_interval * 1000, key="auto")

    # Button to manually refresh data
    if st.sidebar.button("Refresh Data"):
        update_data()


# Title of the Streamlit dashboard
st.title("Real-time Election Dashboard")
topic_name = "aggregated_votes_per_candidate"

# Display sidebar
sidebar()

# Update and display data on the dashboard
update_data()
