package com.example.hhdiplom.adapters;

import android.content.Context;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.FeedVideoItem;
import com.example.hhdiplom.models.LikeResponse;
import com.example.hhdiplom.models.ResponseRequest;
import com.google.android.exoplayer2.ExoPlayer;
import com.google.android.exoplayer2.MediaItem;
import com.google.android.exoplayer2.Player;
import com.google.android.exoplayer2.ui.PlayerView;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class VideoAdapter extends RecyclerView.Adapter<VideoAdapter.VideoViewHolder> {

    public interface OnVideoInteractionListener {
        void onLikeClicked(FeedVideoItem video, int position);
        void onVideoViewed(FeedVideoItem video);
        void onVacancyClicked(FeedVideoItem video);
    }

    private final Context context;
    private final List<FeedVideoItem> videos;
    private final ExoPlayer player;
    private final OnVideoInteractionListener listener;

    private int currentPlayingPosition = -1;
    private int currentPlayingVideoId = -1;
    private final Set<Integer> viewedPositions = new HashSet<>();
    private final Set<Integer> respondedVacancyIds = new HashSet<>();

    private float lastNonZeroVolume = 1f;
    private VideoViewHolder activeHolder;

    private final Player.Listener playerListener = new Player.Listener() {
        @Override
        public void onIsPlayingChanged(boolean isPlaying) {
            updatePlayPauseIcon();
        }

        @Override
        public void onPlaybackStateChanged(int playbackState) {
            updatePlayPauseIcon();
        }
    };

    public VideoAdapter(Context context,
                        List<FeedVideoItem> videos,
                        ExoPlayer player,
                        OnVideoInteractionListener listener) {
        this.context = context;
        this.videos = videos;
        this.player = player;
        this.listener = listener;

        this.player.setRepeatMode(Player.REPEAT_MODE_ALL);
        this.player.addListener(playerListener);
    }

    @NonNull
    @Override
    public VideoViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(context).inflate(R.layout.item_video, parent, false);
        return new VideoViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull VideoViewHolder holder, int position) {
        FeedVideoItem video = videos.get(position);

        holder.tvDescription.setText(video.getDescription() == null ? "" : video.getDescription());
        updateLikeUi(holder, video.isLiked(), video.getLikesCount());

        bindLikeAction(holder, video);
        bindVacancyAction(holder);
        bindApplyAction(holder, video);
        bindPlayerControls(holder);

        if (!viewedPositions.contains(position)) {
            viewedPositions.add(position);
            listener.onVideoViewed(video);
        }

        if (currentPlayingPosition == position) {
            activeHolder = holder;
            attachAndPlayVideo(video, holder);
            syncVolumeUi(holder);
            updatePlayPauseIcon();
        } else {
            if (activeHolder == holder) {
                activeHolder = null;
                player.pause();
            }
            holder.playerView.setPlayer(null);
            holder.btnPlayPause.setVisibility(View.VISIBLE);
            holder.btnPlayPause.setImageResource(android.R.drawable.ic_media_play);
        }
    }

    private void bindLikeAction(@NonNull VideoViewHolder holder, @NonNull FeedVideoItem video) {
        holder.btnLike.setOnClickListener(v -> {
            int adapterPosition = holder.getBindingAdapterPosition();
            if (adapterPosition == RecyclerView.NO_POSITION) {
                return;
            }

            FeedVideoItem currentVideo = videos.get(adapterPosition);
            ApiService api = ApiClient.getApiService();

            api.likeVideo(currentVideo.getId()).enqueue(new Callback<LikeResponse>() {
                @Override
                public void onResponse(@NonNull Call<LikeResponse> call,
                                       @NonNull Response<LikeResponse> response) {
                    if (!response.isSuccessful() || response.body() == null) {
                        return;
                    }

                    boolean liked = response.body().isLiked();
                    currentVideo.setLiked(liked);
                    int likes = currentVideo.getLikesCount();
                    currentVideo.setLikesCount(liked ? likes + 1 : Math.max(likes - 1, 0));

                    updateLikeUi(holder, liked, currentVideo.getLikesCount());

                    listener.onLikeClicked(currentVideo, adapterPosition);
                }

                @Override
                public void onFailure(@NonNull Call<LikeResponse> call, @NonNull Throwable t) {
                }
            });
        });
    }

    private void bindVacancyAction(@NonNull VideoViewHolder holder) {
        holder.btnVacancy.setOnClickListener(v -> {
            int adapterPosition = holder.getBindingAdapterPosition();
            if (adapterPosition == RecyclerView.NO_POSITION) {
                return;
            }
            listener.onVacancyClicked(videos.get(adapterPosition));
        });
    }

    private void bindApplyAction(@NonNull VideoViewHolder holder, @NonNull FeedVideoItem video) {
        if (!"applicant".equalsIgnoreCase(ApiClient.getUserType())) {
            holder.btnApply.setVisibility(View.GONE);
            return;
        }

        holder.btnApply.setVisibility(View.VISIBLE);

        Integer vacancyId = extractVacancyId(video);
        if (vacancyId == null || vacancyId <= 0) {
            holder.btnApply.setEnabled(false);
            holder.btnApply.setText(R.string.video_vacancy_unavailable);
            holder.btnApply.setBackgroundResource(R.drawable.bg_outline_button);
            holder.btnApply.setTextColor(ContextCompat.getColor(context, R.color.white));
            holder.btnApply.setOnClickListener(null);
            return;
        }

        boolean isApplied = respondedVacancyIds.contains(vacancyId)
                || (video.getVacancy() != null && video.getVacancy().isHasApplied());

        if (isApplied) {
            respondedVacancyIds.add(vacancyId);
            if (video.getVacancy() != null) {
                video.getVacancy().setHasApplied(true);
            }
        }

        setApplyButtonState(holder.btnApply, isApplied, false);

        holder.btnApply.setOnClickListener(v -> {
            if (respondedVacancyIds.contains(vacancyId)) {
                return;
            }

            setApplyButtonState(holder.btnApply, false, true);

            ApiClient.getApiService().createResponse(new ResponseRequest(vacancyId)).enqueue(new Callback<Void>() {
                @Override
                public void onResponse(@NonNull Call<Void> call, @NonNull Response<Void> response) {
                    if (response.isSuccessful() || response.code() == 400) {
                        respondedVacancyIds.add(vacancyId);
                        markVideoVacancyAsApplied(vacancyId);
                        notifyItemsByVacancy(vacancyId);

                        if (response.isSuccessful()) {
                            Toast.makeText(context, context.getString(R.string.video_apply_success), Toast.LENGTH_SHORT).show();
                        } else {
                            Toast.makeText(context, context.getString(R.string.video_apply_already), Toast.LENGTH_SHORT).show();
                        }
                        return;
                    }

                    int code = response.code();
                    setApplyButtonState(holder.btnApply, false, false);
                    Toast.makeText(context, context.getString(R.string.video_apply_error, code), Toast.LENGTH_SHORT).show();
                }

                @Override
                public void onFailure(@NonNull Call<Void> call, @NonNull Throwable t) {
                    setApplyButtonState(holder.btnApply, false, false);
                    Toast.makeText(context, context.getString(R.string.error_network_with_message, t.getMessage()), Toast.LENGTH_SHORT).show();
                }
            });
        });
    }

    private void bindPlayerControls(@NonNull VideoViewHolder holder) {
        holder.playerView.setOnClickListener(v -> togglePlayPause());

        holder.btnPlayPause.setOnClickListener(v -> togglePlayPause());

        holder.btnMute.setOnClickListener(v -> {
            if (!isHolderActive(holder)) {
                return;
            }
            toggleMute();
        });
    }

    private void attachAndPlayVideo(@NonNull FeedVideoItem video, @NonNull VideoViewHolder holder) {
        String rawUrl = video.getVideoUrl();
        String url = normalizeVideoUrl(rawUrl);

        if (url == null || url.trim().isEmpty()) {
            holder.playerView.setPlayer(null);
            currentPlayingVideoId = -1;
            return;
        }

        holder.playerView.setPlayer(player);
        holder.playerView.setShutterBackgroundColor(android.graphics.Color.TRANSPARENT);

        int videoId = video.getId();
        if (currentPlayingVideoId != videoId) {
            MediaItem mediaItem = MediaItem.fromUri(url);
            player.setMediaItem(mediaItem);
            player.prepare();
            currentPlayingVideoId = videoId;
        }

        player.play();
    }

    private void updateLikeUi(@NonNull VideoViewHolder holder, boolean isLiked, int likesCount) {
        holder.btnLike.setImageResource(isLiked
                ? R.drawable.ic_favorite_filled
                : R.drawable.ic_favorite_border);
        holder.btnLike.setColorFilter(ContextCompat.getColor(
                context,
                isLiked ? R.color.video_like_active : android.R.color.white
        ));
        holder.tvLikes.setText(String.valueOf(likesCount));
        holder.tvLikes.setTextColor(ContextCompat.getColor(
                context,
                isLiked ? R.color.video_like_active : android.R.color.white
        ));
    }

    private void togglePlayPause() {
        if (activeHolder == null) {
            return;
        }

        if (player.isPlaying()) {
            player.pause();
        } else {
            player.play();
        }
        updatePlayPauseIcon();
    }

    private void toggleMute() {
        float current = player.getVolume();
        if (current <= 0.01f) {
            float restore = lastNonZeroVolume <= 0.01f ? 1f : lastNonZeroVolume;
            player.setVolume(restore);
        } else {
            lastNonZeroVolume = current;
            player.setVolume(0f);
        }

        if (activeHolder != null) {
            syncVolumeUi(activeHolder);
        }
    }

    private void syncVolumeUi(@NonNull VideoViewHolder holder) {
        updateMuteIcon(holder.btnMute, player.getVolume());
    }

    private void updateMuteIcon(@NonNull ImageButton button, float volume) {
        button.setImageResource(volume <= 0.01f
                ? android.R.drawable.ic_lock_silent_mode
                : android.R.drawable.ic_lock_silent_mode_off);
    }

    private void updatePlayPauseIcon() {
        if (activeHolder == null) {
            return;
        }

        if (player.isPlaying()) {
            activeHolder.btnPlayPause.setVisibility(View.GONE);
            return;
        }

        activeHolder.btnPlayPause.setVisibility(View.VISIBLE);
        activeHolder.btnPlayPause.setImageResource(android.R.drawable.ic_media_play);
    }

    private boolean isHolderActive(@NonNull VideoViewHolder holder) {
        return activeHolder == holder && holder.getBindingAdapterPosition() == currentPlayingPosition;
    }

    private void setApplyButtonState(@NonNull Button button, boolean isApplied, boolean isLoading) {
        if (isLoading) {
            button.setEnabled(false);
            button.setText(R.string.video_apply_sending);
            button.setBackgroundResource(R.drawable.bg_apply_button);
            button.setTextColor(ContextCompat.getColor(context, android.R.color.white));
            return;
        }

        if (isApplied) {
            button.setEnabled(false);
            button.setText(R.string.video_apply_sent);
            button.setBackgroundResource(R.drawable.bg_apply_done_button);
            button.setTextColor(ContextCompat.getColor(context, android.R.color.white));
        } else {
            button.setEnabled(true);
            button.setText(R.string.video_apply_button);
            button.setBackgroundResource(R.drawable.bg_apply_button);
            button.setTextColor(ContextCompat.getColor(context, android.R.color.white));
        }
    }

    private void markVideoVacancyAsApplied(int vacancyId) {
        for (FeedVideoItem item : videos) {
            Integer itemVacancyId = extractVacancyId(item);
            if (itemVacancyId != null && itemVacancyId == vacancyId && item.getVacancy() != null) {
                item.getVacancy().setHasApplied(true);
            }
        }
    }

    private void notifyItemsByVacancy(int vacancyId) {
        for (int i = 0; i < videos.size(); i++) {
            Integer itemVacancyId = extractVacancyId(videos.get(i));
            if (itemVacancyId != null && itemVacancyId == vacancyId) {
                notifyItemChanged(i);
            }
        }
    }

    private Integer extractVacancyId(@NonNull FeedVideoItem item) {
        try {
            if (item.getVacancy() != null) {
                int id = item.getVacancy().getId();
                return id > 0 ? id : null;
            }
        } catch (Exception ignored) {
        }
        return null;
    }

    private String normalizeVideoUrl(String url) {
        if (url == null) {
            return null;
        }
        String normalized = url.trim();
        if (normalized.isEmpty()) {
            return null;
        }

        if (normalized.startsWith("/")) {
            String base = ApiClient.BASE_URL;
            if (!base.endsWith("/")) {
                base = base + "/";
            }
            return base + normalized.substring(1);
        }

        if (!normalized.startsWith("http://") && !normalized.startsWith("https://")) {
            String base = ApiClient.BASE_URL;
            if (!base.endsWith("/")) {
                base = base + "/";
            }
            return base + normalized;
        }

        return normalized;
    }

    @Override
    public int getItemCount() {
        return videos == null ? 0 : videos.size();
    }

    public void playVideoAtPosition(int position) {
        if (position < 0 || position >= getItemCount()) {
            return;
        }

        if (position == currentPlayingPosition
                && activeHolder != null
                && activeHolder.getBindingAdapterPosition() == position) {
            attachAndPlayVideo(videos.get(position), activeHolder);
            syncVolumeUi(activeHolder);
            updatePlayPauseIcon();
            return;
        }

        int old = currentPlayingPosition;
        currentPlayingPosition = position;

        if (old != -1 && old != position) {
            notifyItemChanged(old);
        }
        notifyItemChanged(position);
    }

    @Override
    public void onViewAttachedToWindow(@NonNull VideoViewHolder holder) {
        super.onViewAttachedToWindow(holder);
        int position = holder.getBindingAdapterPosition();
        if (position == RecyclerView.NO_POSITION || position != currentPlayingPosition || position >= videos.size()) {
            return;
        }

        activeHolder = holder;
        attachAndPlayVideo(videos.get(position), holder);
        syncVolumeUi(holder);
        updatePlayPauseIcon();
    }

    @Override
    public void onViewRecycled(@NonNull VideoViewHolder holder) {
        super.onViewRecycled(holder);
        holder.playerView.setPlayer(null);
        if (activeHolder == holder) {
            activeHolder = null;
            player.pause();
        }
    }

    @Override
    public void onDetachedFromRecyclerView(@NonNull RecyclerView recyclerView) {
        super.onDetachedFromRecyclerView(recyclerView);
        player.removeListener(playerListener);
        player.pause();
        activeHolder = null;
        currentPlayingVideoId = -1;
    }

    public static class VideoViewHolder extends RecyclerView.ViewHolder {
        PlayerView playerView;
        TextView tvDescription;
        TextView tvLikes;

        ImageView btnLike;
        ImageView btnVacancy;
        ImageButton btnMute;

        ImageButton btnPlayPause;

        Button btnApply;

        public VideoViewHolder(@NonNull View itemView) {
            super(itemView);
            playerView = itemView.findViewById(R.id.playerView);
            tvDescription = itemView.findViewById(R.id.tvDescription);
            tvLikes = itemView.findViewById(R.id.tvLikes);

            btnLike = itemView.findViewById(R.id.btnLike);
            btnVacancy = itemView.findViewById(R.id.btnVacancy);
            btnMute = itemView.findViewById(R.id.btnMute);

            btnPlayPause = itemView.findViewById(R.id.btnPlayPause);

            btnApply = itemView.findViewById(R.id.btnApply);
        }
    }
}
