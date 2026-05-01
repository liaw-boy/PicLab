const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 4567;
const BASE_URL = process.env.BASE_URL || 'https://flyradar.spkaun.cc';
const UPLOAD_DIR = path.join(__dirname, 'uploads');
const AUTO_DELETE_MS = 15 * 60 * 1000; // 15 分鐘後自動刪除

if (!fs.existsSync(UPLOAD_DIR)) fs.mkdirSync(UPLOAD_DIR, { recursive: true });

// 提供靜態檔案
app.use('/piclab-uploads', express.static(UPLOAD_DIR));

const storage = multer.diskStorage({
    destination: (req, file, cb) => cb(null, UPLOAD_DIR),
    filename: (req, file, cb) => {
        const ext = path.extname(file.originalname) || '.jpg';
        const name = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}${ext}`;
        cb(null, name);
    }
});

const upload = multer({
    storage,
    limits: { fileSize: 20 * 1024 * 1024 },
    fileFilter: (req, file, cb) => {
        const allowed = ['image/jpeg', 'image/png', 'image/webp'];
        cb(null, allowed.includes(file.mimetype));
    }
});

// POST /upload
app.post('/upload', upload.single('image'), (req, res) => {
    if (!req.file) {
        return res.status(400).json({ error: '未收到圖片或格式不支援' });
    }

    const publicUrl = `${BASE_URL}/piclab-uploads/${req.file.filename}`;

    // 15 分鐘後自動刪除
    setTimeout(() => {
        fs.unlink(req.file.path, () => {});
    }, AUTO_DELETE_MS);

    res.json({ url: publicUrl, filename: req.file.filename });
});

// DELETE /upload/:filename（發文後主動刪除）
app.delete('/upload/:filename', (req, res) => {
    const filename = path.basename(req.params.filename);
    const filepath = path.join(UPLOAD_DIR, filename);
    fs.unlink(filepath, (err) => {
        if (err) return res.status(404).json({ error: '檔案不存在' });
        res.json({ ok: true });
    });
});

app.listen(PORT, () => {
    console.log(`PicLab Upload Server running on port ${PORT}`);
});
