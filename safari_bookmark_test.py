#!/usr/bin/env python3
"""
Safari Bookmarks.plist 検証スクリプト

【目的】
Safari非起動時にBookmarks.plistへブックマークを追加し、
Safari起動後に反映されるか、iCloud同期と共存できるかを検証する。

【使い方】
1. Safariを完全に終了する
2. ターミナルで実行:
   python3 safari_bookmark_test.py

3. Safariを起動して「ブックマーク > ブックマークを表示」を開く
4. 「_Raindrop_Test」フォルダとテストブックマーク3件が表示されるか確認
5. iCloud同期オンの場合、iPhoneのSafariにも反映されるか確認
6. Safariを終了→再起動して、ブックマークが消えていないか確認

【ロールバック】
問題が起きた場合:
   python3 safari_bookmark_test.py --restore
"""

import plistlib
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

BOOKMARKS_PATH = Path.home() / "Library" / "Safari" / "Bookmarks.plist"
BACKUP_DIR = Path.home() / "Library" / "Safari" / "Bookmarks_backups"
TEST_FOLDER_NAME = "_Raindrop_Test"

# テスト用ブックマーク
TEST_BOOKMARKS = [
    {"title": "テスト1 - Apple", "url": "https://www.apple.com/"},
    {"title": "テスト2 - Wikipedia", "url": "https://ja.wikipedia.org/"},
    {"title": "テスト3 - GitHub", "url": "https://github.com/"},
]


def check_safari_running():
    """Safariが起動中かどうかチェック"""
    result = subprocess.run(["pgrep", "-x", "Safari"], capture_output=True)
    return result.returncode == 0


def backup_plist():
    """Bookmarks.plistをバックアップ"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"Bookmarks_{timestamp}.plist"
    shutil.copy2(BOOKMARKS_PATH, backup_path)
    print(f"✅ バックアップ作成: {backup_path}")
    return backup_path


def restore_latest_backup():
    """最新のバックアップからリストア"""
    if not BACKUP_DIR.exists():
        print("❌ バックアップが見つかりません")
        return False

    backups = sorted(BACKUP_DIR.glob("Bookmarks_*.plist"))
    if not backups:
        print("❌ バックアップが見つかりません")
        return False

    latest = backups[-1]
    shutil.copy2(latest, BOOKMARKS_PATH)
    print(f"✅ リストア完了: {latest}")
    return True


def make_bookmark_leaf(title, url):
    """ブックマークエントリ（Leaf）を作成"""
    return {
        "WebBookmarkType": "WebBookmarkTypeLeaf",
        "WebBookmarkUUID": str(uuid.uuid4()).upper(),
        "URLString": url,
        "URIDictionary": {
            "title": title,
        },
    }


def make_bookmark_folder(name, children=None):
    """ブックマークフォルダ（List）を作成"""
    return {
        "WebBookmarkType": "WebBookmarkTypeList",
        "WebBookmarkUUID": str(uuid.uuid4()).upper(),
        "Title": name,
        "Children": children or [],
    }


def load_plist():
    """Bookmarks.plistを読み込む"""
    with open(BOOKMARKS_PATH, "rb") as f:
        return plistlib.load(f)


def save_plist(data):
    """Bookmarks.plistを保存（バイナリ形式）"""
    # まずXML形式で書き出し
    with open(BOOKMARKS_PATH, "wb") as f:
        plistlib.dump(data, f, fmt=plistlib.FMT_BINARY)
    print("✅ Bookmarks.plist を保存しました（バイナリ形式）")


def find_bookmarks_bar(data):
    """BookmarksBarを見つける"""
    for child in data.get("Children", []):
        if child.get("Title") == "BookmarksBar":
            return child
    return None


def remove_test_folder(bar):
    """既存のテストフォルダがあれば削除"""
    if "Children" not in bar:
        bar["Children"] = []
        return False

    original_len = len(bar["Children"])
    bar["Children"] = [c for c in bar["Children"] if not (c.get("Title") == TEST_FOLDER_NAME and c.get("WebBookmarkType") == "WebBookmarkTypeList")]
    return len(bar["Children"]) < original_len


def show_current_structure(data):
    """現在のブックマーク構造を表示"""
    print("\n📖 現在のブックマーク構造（トップレベル）:")
    for child in data.get("Children", []):
        title = child.get("Title", "(no title)")
        bm_type = child.get("WebBookmarkType", "?")
        if bm_type == "WebBookmarkTypeList":
            num_children = len(child.get("Children", []))
            print(f"  📁 {title} ({num_children}件)")
            # BookmarksBarの中身も表示
            if title == "BookmarksBar":
                for item in child.get("Children", []):
                    item_title = item.get("Title") or item.get("URIDictionary", {}).get("title", "(no title)")
                    item_type = item.get("WebBookmarkType", "?")
                    if item_type == "WebBookmarkTypeList":
                        n = len(item.get("Children", []))
                        print(f"    📁 {item_title} ({n}件)")
                    else:
                        url = item.get("URLString", "")
                        print(f"    🔗 {item_title} - {url[:50]}")
        elif bm_type == "WebBookmarkTypeProxy":
            print(f"  📋 {title} (Proxy)")
        else:
            url = child.get("URLString", "")
            print(f"  🔗 {title} - {url[:50]}")


def main():
    # --- リストアモード ---
    if "--restore" in sys.argv:
        if check_safari_running():
            print("⚠️  Safariが起動中です。先にSafariを終了してください。")
            sys.exit(1)
        restore_latest_backup()
        return

    # --- 構造確認モード ---
    if "--show" in sys.argv:
        data = load_plist()
        show_current_structure(data)
        return

    # --- メイン: テストブックマーク追加 ---
    print("=" * 50)
    print("Safari Bookmarks.plist 検証スクリプト")
    print("=" * 50)

    # 1. Safariが起動中でないことを確認
    if check_safari_running():
        print("❌ Safariが起動中です。先にSafariを終了してください。")
        sys.exit(1)
    print("✅ Safari は停止中です")

    # 2. plistの存在確認
    if not BOOKMARKS_PATH.exists():
        print(f"❌ Bookmarks.plistが見つかりません: {BOOKMARKS_PATH}")
        sys.exit(1)
    print(f"✅ Bookmarks.plist を発見: {BOOKMARKS_PATH}")

    # 3. バックアップ
    backup_path = backup_plist()

    # 4. plist読み込み
    data = load_plist()
    show_current_structure(data)

    # 5. BookmarksBarを探す
    bar = find_bookmarks_bar(data)
    if bar is None:
        print("❌ BookmarksBar が見つかりません")
        sys.exit(1)

    # 6. 既存のテストフォルダがあれば削除（冪等性）
    if remove_test_folder(bar):
        print(f"ℹ️  既存の「{TEST_FOLDER_NAME}」フォルダを削除しました")

    # 7. テストフォルダ＋ブックマークを作成
    test_children = [make_bookmark_leaf(bm["title"], bm["url"]) for bm in TEST_BOOKMARKS]
    test_folder = make_bookmark_folder(TEST_FOLDER_NAME, test_children)

    # 8. BookmarksBarに追加
    bar["Children"].append(test_folder)

    # 9. 保存
    save_plist(data)

    # 10. 結果表示
    print(f"\n🎉 「{TEST_FOLDER_NAME}」フォルダに{len(TEST_BOOKMARKS)}件のテストブックマークを追加しました！")
    print()
    print("【次のステップ】")
    print("1. Safariを起動する")
    print("2. ブックマークバーまたは「ブックマーク > ブックマークを表示」を確認")
    print(f"3. 「{TEST_FOLDER_NAME}」フォルダとテストブックマーク3件があるか確認")
    print("4. iCloud同期オンなら、iPhoneのSafariにも反映されるか確認")
    print("5. Safariを終了→再起動して、消えていないか確認")
    print()
    print("【問題が起きた場合】")
    print("  python3 safari_bookmark_test.py --restore")
    print(f"  (バックアップ: {backup_path})")


if __name__ == "__main__":
    main()
