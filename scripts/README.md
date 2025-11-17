### Generate key (Windows)
```
cmd /c "echo. | ssh-keygen -t ed25519 -C trakt-lists -f C:\ProgramData\ue\.ssh\refresh_streams_d_playlist"
```

### Show public key
```
Get-Content -Raw "C:\ProgramData\ue\.ssh\refresh_streams_d_playlist.pub"
```

### Refresh streams d_playlist (Termux)
```
curl -fsSL https://raw.githubusercontent.com/dtvabrand/entertainment/main/scripts/refresh_streams_d_playlist.sh | bash
```
