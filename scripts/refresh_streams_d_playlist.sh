set -e

pkg install -y git python cronie
pip install yt-dlp

mkdir -p ~/.termux/boot
cat << 'EOF' > ~/.termux/boot/start-cron.sh
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
crond
EOF
chmod +x ~/.termux/boot/start-cron.sh
crond

mkdir -p ~/.ssh
chmod 700 ~/.ssh

echo "Now nano will open for the SSH private key."
echo "Paste your SSH private key, then save and exit."
read -p "Press ENTER to open nano..." _
nano ~/.ssh/refresh_streams_d_playlist
chmod 600 ~/.ssh/refresh_streams_d_playlist

cat << 'EOF' > ~/.ssh/config
Host github.com
  IdentityFile ~/.ssh/refresh_streams_d_playlist
  StrictHostKeyChecking no
EOF
chmod 600 ~/.ssh/config

mkdir -p ~/ue_refresh

cat << 'EOF' > ~/ue_refresh/refresh_streams_d_playlist.sh
#!/data/data/com.termux/files/usr/bin/bash

check_net(){ curl -s --max-time 5 http://clients3.google.com/generate_204 >/dev/null; }

tries=0
until check_net || [ \$tries -ge 18 ]; do sleep 10; tries=\$((tries+1)); done
check_net || exit 0

TEMP_DIR=\$(mktemp -d)
cd "\$TEMP_DIR" || exit 0

git clone --depth=1 git@github.com:dtvabrand/entertainment.git repo
cd repo || exit 0

python3 -m pip install -q yt-dlp --target ./pkgs
export PYTHONPATH="./pkgs"

STATUS=\$(python3 << 'PYEOF'
from yt_dlp import YoutubeDL as Y
P="d_playlist.m3u8"; U="https://www.tvdream.net/web-tv/tvoggi-salerno/"; M=",Tv Oggi"
i=Y({'quiet':1,'skip_download':1,'noplaylist':1,'forceurl':1}).extract_info(U, download=False)
cand=[i.get('url','')] + [f.get('url','') for f in (i.get('formats') or []) if f.get('url')]
m=next(s for s in cand if s and 'tvoggi_aac' in s and '.m3u8' in s and ('token=' in s or 'expires=' in s))
a=open(P,encoding='utf-8').read().splitlines()
k=next((i for i,l in enumerate(a) if l.startswith('#EXTINF') and M in l),-1)+1
changed=False
if 0<k<len(a) and a[k].strip()!=m:
    a[k]=m
    with open(P,'w',encoding='utf-8',newline='\n') as f: f.write('\\n'.join(a)+'\\n')
    changed=True
print('changed' if changed else 'unchanged')
PYEOF
)

if [ "\$STATUS" = "changed" ]; then
  git config user.name  "github-actions[bot]"
  git config user.email "github-actions[bot]@users.noreply.github.com"
  git add d_playlist.m3u8
  git commit -m "Streams refreshed for d_playlist! 📺"
  git push
fi

cd ~
rm -rf "\$TEMP_DIR"
exit 0
EOF

chmod +x ~/ue_refresh/refresh_streams_d_playlist.sh

CRONLINE='0 14 * * * /data/data/com.termux/files/home/ue_refresh/refresh_streams_d_playlist.sh >/dev/null 2>&1'
( crontab -l 2>/dev/null | grep -v 'refresh_streams_d_playlist.sh' ; echo "$CRONLINE" ) | crontab -

echo "To test manually:"
echo "~/ue_refresh/refresh_streams_d_playlist.sh"
