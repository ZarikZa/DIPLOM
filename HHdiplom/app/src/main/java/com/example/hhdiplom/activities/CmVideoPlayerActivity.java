package com.example.hhdiplom.activities;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.example.hhdiplom.R;
import com.google.android.exoplayer2.ExoPlayer;
import com.google.android.exoplayer2.MediaItem;
import com.google.android.exoplayer2.Player;
import com.google.android.exoplayer2.ui.PlayerView;

public class CmVideoPlayerActivity extends AppCompatActivity {

    private PlayerView playerView;
    private ExoPlayer player;

    private String videoUrl;
    private int vacancyId;
    private String vacancyTitle;

    private int likesCount;
    private boolean isLiked = false; // пока локально (хочешь — подключу API)

    private TextView tvVacancyTitle;
    private TextView tvLikes;
    private ImageView btnLike;
    private ImageView btnOpenVacancy;
    private LinearLayout blockVacancy;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_cm_video_player);

        playerView = findViewById(R.id.playerView);
        ImageView btnBack = findViewById(R.id.btnBack);

        tvVacancyTitle = findViewById(R.id.tvVacancyTitle);
        tvLikes = findViewById(R.id.tvLikes);
        btnLike = findViewById(R.id.btnLike);
        btnOpenVacancy = findViewById(R.id.btnOpenVacancy);
        blockVacancy = findViewById(R.id.blockVacancy);

        btnBack.setOnClickListener(v -> finish());

        // ✅ Достаём данные из Intent
        videoUrl = getIntent().getStringExtra("video_url");
        vacancyId = getIntent().getIntExtra("vacancy_id", 0);
        vacancyTitle = getIntent().getStringExtra("vacancy_title");
        likesCount = getIntent().getIntExtra("likes_count", 0);
        isLiked = getIntent().getBooleanExtra("is_liked", false);

        if (videoUrl == null || videoUrl.trim().isEmpty()) {
            Toast.makeText(this, "Пустой URL видео", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        // ✅ UI
        if (vacancyTitle == null || vacancyTitle.trim().isEmpty()) {
            vacancyTitle = (vacancyId > 0) ? ("Вакансия #" + vacancyId) : "Вакансия";
        }
        tvVacancyTitle.setText(vacancyTitle);
        tvLikes.setText(String.valueOf(likesCount));
        btnLike.setImageResource(isLiked ? R.drawable.ic_favorite_filled : R.drawable.ic_favorite_border);

        // ✅ Переход на вакансию (кнопка справа и весь блок слева)
        Runnable openVacancy = () -> {
            if (vacancyId <= 0) {
                Toast.makeText(this, "vacancy_id не передан", Toast.LENGTH_SHORT).show();
                return;
            }
            Intent i = new Intent(this, VacancyDetailsActivity.class);
            i.putExtra("vacancy_id", vacancyId);
            startActivity(i);
        };

        btnOpenVacancy.setOnClickListener(v -> openVacancy.run());
        blockVacancy.setOnClickListener(v -> openVacancy.run());

        // ✅ Лайк (пока локально)
        btnLike.setOnClickListener(v -> {
            isLiked = !isLiked;
            if (isLiked) likesCount++;
            else likesCount = Math.max(likesCount - 1, 0);

            tvLikes.setText(String.valueOf(likesCount));
            btnLike.setImageResource(isLiked ? R.drawable.ic_favorite_filled : R.drawable.ic_favorite_border);

            // если хочешь — сюда добавим реальный API запрос like/unlike
        });

        // ✅ ExoPlayer
        player = new ExoPlayer.Builder(this).build();
        player.setRepeatMode(Player.REPEAT_MODE_ONE);
        playerView.setPlayer(player);

        playerView.setOnClickListener(v -> {
            if (player == null) return;
            if (player.isPlaying()) player.pause();
            else player.play();
        });

        MediaItem item = MediaItem.fromUri(Uri.parse(videoUrl));
        player.setMediaItem(item);
        player.prepare();
        player.play();
    }

    @Override
    protected void onStop() {
        super.onStop();
        if (player != null) player.pause();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (player != null) {
            playerView.setPlayer(null);
            player.release();
            player = null;
        }
    }
}
