"""
Zotero论文导入脚本
将精选文献导入Zotero的"书法机器人"文件夹 (collectionID=5)
"""
import sqlite3
import os
import random
import string
import time
import urllib.request
import json

ZOTERO_DATA = r"D:\basic data\zotero"
ZOTERO_DB = os.path.join(ZOTERO_DATA, "zotero.sqlite")
STORAGE_DIR = os.path.join(ZOTERO_DATA, "storage")
COLLECTION_ID = 5  # 书法机器人

def gen_key():
    """Generate Zotero-style 8-char key"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(8))

def get_timestamp():
    return int(time.time() * 1000)

def insert_item(conn, item_type_id, date_added, key, library_id=1):
    ts = get_timestamp()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO items (itemTypeID, dateAdded, dateModified, clientDateModified, libraryID, key, version, synced) "
        "VALUES (?, ?, ?, ?, ?, ?, 0, 0)",
        (item_type_id, ts, ts, ts, library_id, key)
    )
    item_id = cur.lastrowid
    return item_id

def insert_value(conn, value):
    """Insert a value into itemDataValues if not exists, return valueID"""
    cur = conn.cursor()
    cur.execute("SELECT valueID FROM itemDataValues WHERE value = ?", (value,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO itemDataValues (value) VALUES (?)", (value,))
    return cur.lastrowid

def set_field(conn, item_id, field_id, value):
    if value is None or value == "":
        return
    value_id = insert_value(conn, value)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO itemData (itemID, fieldID, valueID) VALUES (?, ?, ?)",
        (item_id, field_id, value_id)
    )

def add_creator(conn, item_id, first_name, last_name, creator_type_id=8, order_index=0):
    """Add an author creator. type 8 = author"""
    cur = conn.cursor()
    # Check if creator exists
    cur.execute("SELECT creatorID FROM creators WHERE firstName=? AND lastName=?",
                (first_name, last_name))
    row = cur.fetchone()
    if row:
        creator_id = row[0]
    else:
        cur.execute("INSERT INTO creators (firstName, lastName, fieldMode) VALUES (?, ?, 0)",
                    (first_name, last_name))
        creator_id = cur.lastrowid

    cur.execute(
        "INSERT INTO itemCreators (itemID, creatorID, creatorTypeID, orderIndex) VALUES (?, ?, ?, ?)",
        (item_id, creator_id, creator_type_id, order_index)
    )

def add_to_collection(conn, item_id, collection_id=COLLECTION_ID):
    cur = conn.cursor()
    cur.execute("SELECT MAX(orderIndex) FROM collectionItems WHERE collectionID=?", (collection_id,))
    row = cur.fetchone()
    next_order = (row[0] or 0) + 1
    cur.execute(
        "INSERT INTO collectionItems (collectionID, itemID, orderIndex) VALUES (?, ?, ?)",
        (collection_id, item_id, next_order)
    )

def add_attachment(conn, item_id, file_path):
    """Add a PDF attachment"""
    ts = get_timestamp()
    key = gen_key()
    cur = conn.cursor()

    # Create the storage directory
    storage_key = gen_key()
    storage_path = os.path.join(STORAGE_DIR, storage_key)
    os.makedirs(storage_path, exist_ok=True)

    # Copy PDF to storage
    dest = os.path.join(storage_path, os.path.basename(file_path))
    if not os.path.exists(dest):
        import shutil
        shutil.copy2(file_path, dest)

    # Insert attachment item
    cur.execute(
        "INSERT INTO items (itemTypeID, dateAdded, dateModified, clientDateModified, libraryID, key, version, synced) "
        "VALUES (3, ?, ?, ?, 1, ?, 0, 0)",
        (ts, ts, ts, key)
    )
    attach_id = cur.lastrowid

    # Link with parent item
    rel_path = f"storage:{storage_key}/{os.path.basename(file_path)}"
    cur.execute(
        "INSERT INTO itemAttachments (itemID, parentItemID, linkMode, contentType, charsetID, path, syncState, storageModTime) "
        "VALUES (?, ?, 0, 'application/pdf', 0, ?, 0, ?)",
        (attach_id, item_id, rel_path, ts)
    )

    # Set title field for attachment
    set_field(conn, attach_id, 1, os.path.basename(file_path))

    return attach_id

def download_pdf(url, filename, save_dir):
    """Download a PDF file"""
    os.makedirs(save_dir, exist_ok=True)
    filepath = os.path.join(save_dir, filename)
    if os.path.exists(filepath):
        print(f"  PDF already exists: {filepath}")
        return filepath
    try:
        print(f"  Downloading: {url}")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            with open(filepath, 'wb') as f:
                f.write(response.read())
        print(f"  Saved: {filepath}")
        return filepath
    except Exception as e:
        print(f"  Download failed: {e}")
        return None

# ============================================================
# Paper definitions
# ============================================================

papers = [
    {
        "type": 11,  # conferencePaper
        "title": "Application of Stroke Extraction and Trajectory Planning in Robotic Calligraphy",
        "authors": [
            ("Yuzhi", "Wu"), ("Jiashu", "Feng"), ("Wangcheng", "Chen"), ("Yisheng", "Guan")
        ],
        "fields": {
            57: "2024 17th International Conference on Intelligent Robotics and Applications (ICIRA)",  # proceedingsTitle
            58: "International Conference on Intelligent Robotics and Applications (ICIRA)",  # conferenceName
            6: "2025",  # date
            59: "10.1007/978-981-96-0774-7_23",  # DOI
            32: "308-320",  # pages
            2: "Takes a text image input from copybook or field writing, uses image processing and CNN to segment characters and recognize strokes, skeletonizes strokes, then employs dynamic path planning to generate trajectory point sequences for robot control.",  # abstract
            13: "https://doi.org/10.1007/978-981-96-0774-7_23",  # url
        },
        "downloads": []  # Springer - need institutional access
    },
    {
        "type": 11,  # conferencePaper
        "title": "CalliRewrite: Recovering Handwriting Behaviors from Calligraphy Images without Supervision",
        "authors": [
            ("Yuxuan", "Luo"), ("Zekun", "Wu"), ("Zhouhui", "Lian")
        ],
        "fields": {
            57: "2024 IEEE International Conference on Robotics and Automation (ICRA)",  # proceedingsTitle
            58: "IEEE International Conference on Robotics and Automation (ICRA)",  # conferenceName
            6: "2024",  # date
            59: "10.1109/ICRA57147.2024.10611477",  # DOI
            32: "8671-8678",  # pages
            2: "A coarse-to-fine approach to recover plausible writing orders from calligraphy images without labeled demonstrations. Uses an unsupervised CNN-LSTM image-to-sequence model for coarse stroke decomposition and Reinforcement Learning (SAC) to fine-tune stylized trajectory generation for robotic arm control.",  # abstract
            13: "https://arxiv.org/abs/2405.15776",  # url
        },
        "downloads": [
            ("https://arxiv.org/pdf/2405.15776", "CalliRewrite_2024.pdf")
        ]
    },
    {
        "type": 22,  # journalArticle
        "title": "B-BSMG: Bézier Brush Stroke Model-Based Generator for Robotic Chinese Calligraphy",
        "authors": [
            ("Dongmei", "Guo"), ("Guang", "Yan")
        ],
        "fields": {
            38: "International Journal of Computational Intelligence Systems",  # publicationTitle
            19: "17",  # volume
            6: "2024",  # date
            59: "10.1007/s44196-024-00499-4",  # DOI
            32: "104",  # pages (article number)
            2: "A Bézier brush stroke model parameterized by robotic arm control parameters (h, α, β). Uses a neural network generator (B-BSMG) to produce brush stroke images for robotic writing.",  # abstract
            13: "https://doi.org/10.1007/s44196-024-00499-4",  # url
        },
        "downloads": []
    },
    {
        "type": 11,  # conferencePaper
        "title": "SPSOC: Staged Pseudo-Spectral Optimal Control Optimization Model for Robotic Chinese Calligraphy",
        "authors": [
            ("Dongmei", "Guo"), ("Huasong", "Min"), ("Guang", "Yan")
        ],
        "fields": {
            57: "2023 International Conference on Intelligent Robotics and Applications (ICIRA)",  # proceedingsTitle
            58: "International Conference on Intelligent Robotics and Applications (ICIRA)",  # conferenceName
            6: "2023",  # date
            59: "10.1007/978-981-99-6492-5_36",  # DOI
            32: "416-428",  # pages
            2: "Formulates robot calligraphy as a trajectory optimization problem using pseudo-spectral optimal control (PSOC). Stroke skeleton curves are fitted by least squares, and a three-stage model (qibi, xingbi, shoubi) is incorporated.",  # abstract
            13: "https://doi.org/10.1007/978-981-99-6492-5_36",  # url
        },
        "downloads": []
    },
    {
        "type": 22,  # journalArticle
        "title": "Brush Stroke-Based Writing Trajectory Control Model for Robotic Chinese Calligraphy",
        "authors": [
            ("Dongmei", "Guo"), ("Wenjun", "Fang"), ("Wenwen", "Yang")
        ],
        "fields": {
            38: "Electronics",  # publicationTitle
            19: "14",  # volume
            76: "15",  # issue
            6: "2025",  # date
            59: "10.3390/electronics14153000",  # DOI
            2: "Fine-grained trajectory control based on Composite-Curve-Dilation Brush Stroke Model (CCD-BSM). Decomposes writing into initiation (qibi), execution (xingbi), and completion (shoubi) stages. Achieves 99.54% Cosine Similarity and 97.57% SSIM.",  # abstract
            13: "https://doi.org/10.3390/electronics14153000",  # url
            79: "2079-9292",  # ISSN
        },
        "downloads": [
            ("https://mdpi-res.com/electronics/electronics-14-03000/article_deploy/electronics-14-03000.pdf", "CCDBSM_2025.pdf")
        ]
    },
    {
        "type": 22,  # journalArticle
        "title": "Solving Robotic Trajectory Sequential Writing Problem via Learning Character's Structural and Sequential Information",
        "authors": [
            ("Quanfeng", "Li"), ("Zhihua", "Guo"), ("Fei", "Chao"), ("Xiang", "Chang"),
            ("Longzhi", "Yang"), ("Chih-Min", "Lin"), ("Changjing", "Shang"), ("Qiang", "Shen")
        ],
        "fields": {
            38: "IEEE Transactions on Cybernetics",  # publicationTitle
            19: "54",  # volume
            76: "2",  # issue
            6: "2024",  # date
            59: "10.1109/TCYB.2022.3194700",  # DOI
            32: "1096-1108",  # pages
            2: "Applies a GRU network to generate robotic writing actions from prelabeled trajectory sequence vectors. Uses swarm optimization for hyperparameter tuning. Evaluated with Arabic numerals across FID, MAE, PSNR, SSIM, and PerLoss metrics.",  # abstract
            13: "https://doi.org/10.1109/TCYB.2022.3194700",  # url
        },
        "downloads": []
    },
    {
        "type": 22,  # journalArticle
        "title": "Internal Model Control Structure Inspired Robotic Calligraphy System",
        "authors": [
            ("Ruiqi", "Wu"), ("Fei", "Chao"), ("Changle", "Zhou"), ("Xiang", "Chang"),
            ("Longzhi", "Yang"), ("Changjing", "Shang"), ("Zhaojie", "Zhang"), ("Qiang", "Shen")
        ],
        "fields": {
            38: "IEEE Transactions on Industrial Informatics",  # publicationTitle
            19: "20",  # volume
            76: "2",  # issue
            6: "2024",  # date
            59: "10.1109/TII.2023.3292972",  # DOI
            32: "2600-2610",  # pages
            2: "A vision-motor network and motor-vision network inspired by Internal Model Control (IMC) for robotic hand-eye coordination. The vision-motor network converts image inputs to robotic actions (trajectories).",  # abstract
            13: "https://doi.org/10.1109/TII.2023.3292972",  # url
        },
        "downloads": []
    },
    {
        "type": 11,  # conferencePaper
        "title": "An Image-Based Imitation Learning Framework for Robotic Writing Tasks",
        "authors": [
            ("Wenjin", "Xu"), ("Xiaolong", "Li"), ("Qingmin", "Li"), ("Chenguang", "Yang")
        ],
        "fields": {
            57: "2024 30th International Conference on Mechatronics and Machine Vision in Practice (M2VIP)",  # proceedingsTitle
            6: "2024",  # date
            59: "10.1109/M2VIP62491.2024.10746145",  # DOI
            2: "Transforms static calligraphy images into dynamic formats using Gaussian Mixture Models (GMM) and Dynamic Movement Primitives (DMP) for imitation learning of stroke thickness and writing skills.",  # abstract
            13: "https://doi.org/10.1109/M2VIP62491.2024.10746145",  # url
        },
        "downloads": []
    },
    {
        "type": 22,  # journalArticle
        "title": "Robotic Writing of Arbitrary Unicode Characters Using Paintbrushes",
        "authors": [
            ("David Silvan", "Zingrebe"), ("Jörg Marvin", "Gülzow"), ("Oliver", "Deussen")
        ],
        "fields": {
            38: "Robotics",  # publicationTitle
            19: "12",  # volume
            76: "3",  # issue
            6: "2023",  # date
            59: "10.3390/robotics12030072",  # DOI
            2: "A two-stage pipeline extracting Voronoi Medial Axis skeleton from glyph outlines to obtain stroke centerlines. Skeleton is normalized, intersections fixed, and greedy stroke extraction produces paintable strokes. A brush model compensates for brush lag and computes required pressure.",  # abstract
            13: "https://doi.org/10.3390/robotics12030072",  # url
            79: "2218-6581",  # ISSN
        },
        "downloads": [
            ("https://mdpi-res.com/robotics/robotics-12-00072/article_deploy/robotics-12-00072.pdf", "VMA_Skeleton_Robotic_Writing_2023.pdf")
        ]
    },
    {
        "type": 22,  # journalArticle
        "title": "Physically Motivated Model of a Painting Brush for Robotic Painting and Calligraphy",
        "authors": [
            ("Artur", "Karimov"), ("Maksim", "Strelnikov"), ("Sergei", "Mazin"),
            ("Dmitriy", "Goryunov"), ("Sergey", "Leonov"), ("Denis", "Butusov")
        ],
        "fields": {
            38: "Robotics",  # publicationTitle
            19: "13",  # volume
            76: "6",  # issue
            6: "2024",  # date
            59: "10.3390/robotics13060094",  # DOI
            2: "Physically derived brush compliance model (brush footprint vs. pressure), brush lag modeling, and calibration methods for trajectory planning in robotic painting and calligraphy.",  # abstract
            13: "https://doi.org/10.3390/robotics13060094",  # url
            79: "2218-6581",  # ISSN
        },
        "downloads": [
            ("https://mdpi-res.com/robotics/robotics-13-00094/article_deploy/robotics-13-00094.pdf", "Physical_Brush_Model_2024.pdf")
        ]
    },
    {
        "type": 31,  # preprint
        "title": "End-to-end Manipulator Calligraphy Planning via Variational Imitation Learning",
        "authors": [
            ("Fangping", "Xie"), ("Pierre", "Le Meur"), ("Charith", "Fernando")
        ],
        "fields": {
            6: "2023",  # date
            59: "10.48550/arXiv.2304.02801",  # DOI
            2: "End-to-end manipulator calligraphy planning using 3D trajectory representation with pen tip rotation. Network structure: VAE + Bi-LSTM + MLP, learning from expert demonstrations (image + pose data) via imitation learning.",  # abstract
            13: "https://arxiv.org/abs/2304.02801",  # url
            104: "arXiv",  # institution (as repository)
        },
        "downloads": [
            ("https://arxiv.org/pdf/2304.02801", "VI_Calligraphy_2023.pdf")
        ]
    },
    {
        "type": 31,  # preprint
        "title": "Sim-to-Real Brush Manipulation Using Behavior Cloning and Reinforcement Learning",
        "authors": [
            ("Biao", "Jia"), ("Dinesh", "Manocha")
        ],
        "fields": {
            6: "2023",  # date
            2: "Bridges sim-to-real gap for brush manipulation using behavior cloning + RL. Trains a painting agent in a virtual environment (MyPaint) and transfers to a real robotic arm with a brush on high-dimensional continuous action spaces.",  # abstract
            13: "https://arxiv.org/abs/2309",  # url
            104: "arXiv",  # institution
        },
        "downloads": []
    },
]

# ============================================================
# Main import logic
# ============================================================

def main():
    conn = sqlite3.connect(ZOTERO_DB)

    # Download directory
    dl_dir = os.path.join(os.path.dirname(__file__), "downloads")

    imported = 0
    for p in papers:
        key = gen_key()
        item_id = insert_item(conn, p["type"], get_timestamp(), key)
        print(f"\nInserting: {p['title'][:80]}...")
        print(f"  itemID={item_id}, key={key}")

        # Set title
        set_field(conn, item_id, 1, p["title"])

        # Set fields
        for field_id, value in p["fields"].items():
            set_field(conn, item_id, field_id, value)

        # Add authors
        for i, (first, last) in enumerate(p["authors"]):
            add_creator(conn, item_id, first, last, 8, i)

        # Add to collection
        add_to_collection(conn, item_id, COLLECTION_ID)

        # Download PDFs
        for url, filename in p["downloads"]:
            pdf_path = download_pdf(url, filename, dl_dir)
            if pdf_path:
                try:
                    add_attachment(conn, item_id, pdf_path)
                    print(f"  PDF attached: {filename}")
                except Exception as e:
                    print(f"  Attachment failed: {e}")

        imported += 1

    conn.commit()
    conn.close()
    print(f"\n=== Done! Imported {imported} papers to Zotero 书法机器人 folder ===")
    print(f"PDFs saved to: {dl_dir}")

if __name__ == "__main__":
    main()
