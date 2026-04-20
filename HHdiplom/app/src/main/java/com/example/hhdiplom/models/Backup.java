package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class Backup {
    @SerializedName("id")
    private int id;

    @SerializedName("name")
    private String name;

    @SerializedName("backup_file")
    private String backupFile;

    @SerializedName("backup_type")
    private String backupType; // full, database, media

    @SerializedName("file_size")
    private long fileSize;

    @SerializedName("created_at")
    private String createdAt;

    @SerializedName("created_by")
    private int createdById;

    // Геттеры и сеттеры
    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getBackupFile() { return backupFile; }
    public void setBackupFile(String backupFile) { this.backupFile = backupFile; }

    public String getBackupType() { return backupType; }
    public void setBackupType(String backupType) { this.backupType = backupType; }

    public long getFileSize() { return fileSize; }
    public void setFileSize(long fileSize) { this.fileSize = fileSize; }

    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }

    public int getCreatedById() { return createdById; }
    public void setCreatedById(int createdById) { this.createdById = createdById; }

    // Вспомогательный метод для отображения размера
    public String getFileSizeDisplay() {
        if (fileSize < 1024) {
            return fileSize + " B";
        } else if (fileSize < 1024 * 1024) {
            return String.format("%.2f KB", fileSize / 1024.0);
        } else if (fileSize < 1024 * 1024 * 1024) {
            return String.format("%.2f MB", fileSize / (1024.0 * 1024.0));
        } else {
            return String.format("%.2f GB", fileSize / (1024.0 * 1024.0 * 1024.0));
        }
    }
}