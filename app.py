import pandas as pd
import streamlit as st

st.set_page_config(page_title="Inventory Review", layout="wide")

REQUIRED_COLUMNS = ["sku", "description", "quantity"]


def review_inventory(uploaded):
    inventory = pd.read_csv(
        uploaded,
        dtype="string",
        keep_default_na=False,
        encoding="utf-8-sig",
    )

    inventory.columns = inventory.columns.str.strip()
    if inventory.columns.duplicated().any():
        raise ValueError("Column names must be unique after trimming whitespace.")

    missing = [column for column in REQUIRED_COLUMNS if column not in inventory.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}.")

    inventory = inventory[REQUIRED_COLUMNS].copy()
    for column in REQUIRED_COLUMNS:
        inventory[column] = inventory[column].str.strip()

    # Validate as text to preserve leading zeros in SKUs and avoid rounding quantities.
    valid_quantity = inventory["quantity"].str.fullmatch(r"[0-9]+", na=False)

    issues = [[] for _ in range(len(inventory))]
    checks = [
        (inventory["sku"].eq(""), "Missing SKU"),
        (inventory["description"].eq(""), "Missing description"),
        (~valid_quantity, "Quantity must be a non-negative whole number"),
    ]

    for mask, message in checks:
        for position, flagged in enumerate(mask):
            if flagged:
                issues[position].append(message)

    inventory["Review reason"] = ["; ".join(messages) for messages in issues]
    needs_review = inventory["Review reason"].ne("")

    return (
        inventory.loc[~needs_review, REQUIRED_COLUMNS],
        inventory.loc[needs_review],
    )


st.title("Inventory Review")

if not st.user.is_logged_in:
    st.info("Sign in with your organization account to upload inventory.")
    if st.button("Sign in"):
        st.login()
    st.stop()

# Fail closed: signing in is not enough; the account must also be approved.
allowed_emails = {
    email.strip().casefold()
    for email in st.secrets.get("inventory_access", {}).get("allowed_emails", [])
}
user_email = str(st.user.get("email") or "").strip().casefold()

with st.sidebar:
    if st.button("Sign out"):
        st.logout()

if not user_email or user_email not in allowed_emails:
    st.error("This account is not approved to access the inventory dashboard.")
    st.stop()

uploaded = st.file_uploader("Upload a store inventory CSV", type=["csv"])
st.caption("Required columns: sku, description, quantity. Use UTF-8 encoding.")

if uploaded is None:
    st.stop()

try:
    accepted, review = review_inventory(uploaded)
except pd.errors.EmptyDataError:
    st.error("The file is empty. Upload a CSV with a header and inventory rows.")
    st.stop()
except (pd.errors.ParserError, UnicodeDecodeError):
    st.error("Could not read the file. Check that it is a valid UTF-8 CSV.")
    st.stop()
except ValueError as error:
    st.error(str(error))
    st.stop()

total = len(accepted) + len(review)
if total == 0:
    st.info("The CSV has the required headers but contains no inventory rows.")
    st.stop()

uploaded_metric, accepted_metric, review_metric = st.columns(3)
uploaded_metric.metric("Rows uploaded", total)
accepted_metric.metric("Rows accepted", len(accepted))
review_metric.metric("Rows needing review", len(review))

if not review.empty:
    st.subheader("Rows needing review")
    st.dataframe(review, hide_index=True, height=250)

st.subheader("Accepted inventory")
if accepted.empty:
    st.info("No rows passed validation.")
else:
    st.dataframe(accepted, hide_index=True, height=400)
