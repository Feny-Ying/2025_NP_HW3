import os
import shutil

TEMPLATE_DIR = "template"

def create_new_game(name):
    target_dir = os.path.join("games", name)
    os.makedirs(target_dir, exist_ok=True)
    # 複製 template 到新遊戲
    shutil.copytree(TEMPLATE_DIR, target_dir, dirs_exist_ok=True)
    print(f"New game '{name}' created at {target_dir}")

if __name__ == "__main__":
    game_name = input("Enter new game name: ")
    create_new_game(game_name)