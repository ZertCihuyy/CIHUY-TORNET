import os, subprocess, json, requests, shutil
from tqdm import tqdm
from colorama import Fore, Style, init

init(autoreset=True)

BASE = os.getcwd()
DOWNLOADS = os.path.join(BASE, "downloads")
OUTPUT    = os.path.join(BASE, "output")

os.makedirs(DOWNLOADS, exist_ok=True)
os.makedirs(OUTPUT, exist_ok=True)

# ================= UTIL =================

def run(cmd, show=False):
    if show:
        subprocess.run(cmd)
    else:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def log(msg, c=Fore.CYAN):
    print(c + msg)

# ================= TORRENT =================

def torrent_download():
    log("Pilih input torrent:")
    log("1. Torrent URL / Magnet")
    log("2. File .torrent (path)")

    opt = input("Pilih (1/2): ").strip()

    if opt == "1":
        url = input("Masukkan torrent URL / magnet:\n> ").strip()
        run(["aria2c", "--dir="+DOWNLOADS, url], show=True)

    elif opt == "2":
        path = input("Masukkan path file .torrent:\n> ").strip()
        run(["aria2c", "--dir="+DOWNLOADS, path], show=True)

    else:
        log("Opsi tidak valid", Fore.RED)
        exit()

# ================= PROBE =================

def probe(video):
    data = subprocess.check_output([
        "ffprobe","-loglevel","error",
        "-show_streams","-of","json",video
    ])
    return json.loads(data)["streams"]

def video_codec(video):
    for s in probe(video):
        if s["codec_type"] == "video":
            return s["codec_name"]
    return None

def subtitles(video):
    return [s for s in probe(video) if s["codec_type"] == "subtitle"]

# ================= CONVERT =================

def mkv_to_m3u8(video, out):
    codec = video_codec(video)
    copy = codec in ["h264", "hevc"]

    log("[+] Convert MKV ➜ M3U8 (video + audio)")

    run([
        "ffmpeg","-y","-i",video,
        "-map","0:v","-map","0:a?",
        "-c:v","copy" if copy else "libx264",
        "-preset","veryfast",
        "-c:a","aac","-b:a","128k",
        "-f","hls",
        "-hls_time","6",
        "-hls_playlist_type","vod",
        "-hls_segment_filename",f"{out}/seg_%03d.ts",
        f"{out}/stream.m3u8"
    ], show=True)

def extract_vtt(video, out):
    subs = subtitles(video)
    sdir = os.path.join(out, "subtitles")
    os.makedirs(sdir, exist_ok=True)

    log(f"[+] Subtitle ditemukan: {len(subs)}")

    for i, s in enumerate(subs):
        lang = s.get("tags",{}).get("language",f"sub{i}")
        run([
            "ffmpeg","-y","-i",video,
            "-map",f"0:s:{i}",
            os.path.join(sdir, f"{lang}.vtt")
        ])

# ================= GOFILE =================

def gofile_server():
    return requests.get("https://api.gofile.io/getServer").json()["data"]["server"]

def gofile_upload(folder):
    server = gofile_server()
    links = []

    for root,_,files in os.walk(folder):
        for f in files:
            path = os.path.join(root,f)
            with open(path,"rb") as file:
                r = requests.post(
                    f"https://{server}.gofile.io/uploadFile",
                    files={"file": file}
                ).json()
                links.append(r["data"]["downloadPage"])

    return links

# ================= MAIN =================

def main():
    print(Fore.MAGENTA + """
 ██████╗██╗██╗  ██╗██╗   ██╗██╗   ██╗
██╔════╝██║██║  ██║██║   ██║╚██╗ ██╔╝
██║     ██║███████║██║   ██║ ╚████╔╝ 
██║     ██║██╔══██║██║   ██║  ╚██╔╝  
╚██████╗██║██║  ██║╚██████╔╝   ██║   
 ╚═════╝╚═╝╚═╝  ╚═╝ ╚═════╝    ╚═╝   
        CIHUY-TORNET FULL AUTO
""")

    torrent_download()

    mkvs = []
    for r,_,f in os.walk(DOWNLOADS):
        for x in f:
            if x.endswith(".mkv"):
                mkvs.append(os.path.join(r,x))

    if not mkvs:
        log("❌ MKV tidak ditemukan", Fore.RED)
        return

    for v in tqdm(mkvs, desc="Processing"):
        name = os.path.splitext(os.path.basename(v))[0]
        out  = os.path.join(OUTPUT, name)
        os.makedirs(out, exist_ok=True)

        mkv_to_m3u8(v, out)
        extract_vtt(v, out)

        log("[+] Upload ke gofile.io")
        links = gofile_upload(out)

        log("[✓] LINK GOFILE:", Fore.GREEN)
        for l in links:
            print(" ", l)

        os.remove(v)
        shutil.rmtree(out)

        log("[✓] MKV & output lokal dihapus\n", Fore.GREEN)

    log("=== SELESAI FULL OTOMATIS ===", Fore.MAGENTA)

if __name__ == "__main__":
    main()
