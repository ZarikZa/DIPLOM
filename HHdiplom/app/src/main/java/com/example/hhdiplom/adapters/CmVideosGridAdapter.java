package com.example.hhdiplom.adapters;

import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.PopupMenu;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.bumptech.glide.Glide;
import com.example.hhdiplom.R;
import com.example.hhdiplom.activities.CmVideoPlayerActivity;
import com.example.hhdiplom.activities.VacancyDetailsActivity;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.models.CmVideoItem;

import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class CmVideosGridAdapter extends RecyclerView.Adapter<CmVideosGridAdapter.VH> {

    private final List<CmVideoItem> items;

    public CmVideosGridAdapter(List<CmVideoItem> items) {
        this.items = items;
    }

    @NonNull
    @Override
    public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_cm_video_grid, parent, false);
        return new VH(v);
    }

    @Override
    public void onBindViewHolder(@NonNull VH h, int position) {
        CmVideoItem item = items.get(position);

        String title = item.getVacancyPosition();
        if (title == null || title.trim().isEmpty()) {
            title = item.getVacancyId() > 0 ? ("#" + item.getVacancyId()) : "Видео";
        }
        h.tvVacancy.setText(title);

        // thumbnail из видео
        String url = normalizeVideoUrl(item.getVideoUrl());
        Glide.with(h.imgThumb.getContext())
                .load(url)
                .thumbnail(0.2f)
                .centerCrop()
                .into(h.imgThumb);

        // обычный клик = открыть видео
        h.itemView.setOnClickListener(v -> openPlayer(v.getContext(), item));

        // long press = меню
        h.itemView.setOnLongClickListener(v -> {
            showMenu(v, item, h.getAdapterPosition());
            return true;
        });
    }

    private void showMenu(View anchor, CmVideoItem item, int adapterPos) {
        if (adapterPos == RecyclerView.NO_POSITION) return;

        PopupMenu pm = new PopupMenu(anchor.getContext(), anchor);
        pm.getMenu().add(0, 1, 0, "Открыть");
        pm.getMenu().add(0, 2, 1, "К вакансии");
        pm.getMenu().add(0, 3, 2, "Удалить");

        pm.setOnMenuItemClickListener(mi -> {
            int id = mi.getItemId();
            if (id == 1) {
                openPlayer(anchor.getContext(), item);
                return true;
            }
            if (id == 2) {
                openVacancy(anchor.getContext(), item);
                return true;
            }
            if (id == 3) {
                confirmDelete(anchor.getContext(), item, adapterPos);
                return true;
            }
            return false;
        });

        pm.show();
    }

    private void openPlayer(Context ctx, CmVideoItem item) {
        Intent i = new Intent(ctx, CmVideoPlayerActivity.class);

        i.putExtra("video_url", normalizeVideoUrl(item.getVideoUrl()));
        i.putExtra("video_id", item.getId());

        // ✅ чтобы VacancyDetailsActivity не ругалась — передаём именно "VACANCY_ID"
        i.putExtra("vacancy_id", item.getVacancyId()); // на всякий

        i.putExtra("vacancy_title", item.getVacancyPosition());
        i.putExtra("likes_count", item.getLikesCount());
        i.putExtra("views_count", item.getViewsCount());
        i.putExtra("is_active", item.isActive());

        ctx.startActivity(i);
    }

    private void openVacancy(Context ctx, CmVideoItem item) {
        int vacancyId = item.getVacancyId();
        if (vacancyId <= 0) {
            Toast.makeText(ctx, "vacancy_id не найден", Toast.LENGTH_SHORT).show();
            return;
        }

        Intent i = new Intent(ctx, VacancyDetailsActivity.class);
        i.putExtra("vacancy_id", vacancyId);
        ctx.startActivity(i);
    }

    private void confirmDelete(Context ctx, CmVideoItem item, int adapterPos) {
        new AlertDialog.Builder(ctx)
                .setTitle("Удалить видео?")
                .setMessage("Видео будет удалено безвозвратно.")
                .setPositiveButton("Удалить", (d, w) -> doDelete(ctx, item.getId(), adapterPos))
                .setNegativeButton("Отмена", null)
                .show();
    }

    private void doDelete(Context ctx, int videoId, int adapterPos) {
        ApiClient.getApiService().deleteCmVideo(videoId).enqueue(new Callback<Void>() {
            @Override
            public void onResponse(@NonNull Call<Void> call, @NonNull Response<Void> response) {
                if (response.isSuccessful()) {
                    if (adapterPos >= 0 && adapterPos < items.size()) {
                        items.remove(adapterPos);
                        notifyItemRemoved(adapterPos);
                    } else {
                        notifyDataSetChanged();
                    }
                    Toast.makeText(ctx, "Видео удалено", Toast.LENGTH_SHORT).show();
                } else {
                    Toast.makeText(ctx, "Ошибка удаления: " + response.code(), Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onFailure(@NonNull Call<Void> call, @NonNull Throwable t) {
                Toast.makeText(ctx, "Сеть: " + t.getMessage(), Toast.LENGTH_SHORT).show();
            }
        });
    }

    /**
     * Чиним дубль vacancy_videos и приводим к абсолютному URL
     */
    private String normalizeVideoUrl(String url) {
        if (url == null) return null;
        String u = url.trim();
        if (u.isEmpty()) return null;

        if (u.startsWith("/")) {
            u = com.example.hhdiplom.api.ApiClient.BASE_URL + u.substring(1);
        } else if (!u.startsWith("http://") && !u.startsWith("https://")) {
            u = com.example.hhdiplom.api.ApiClient.BASE_URL + u;
        }
        return u;
    }

    @Override
    public int getItemCount() {
        return items.size();
    }

    static class VH extends RecyclerView.ViewHolder {
        ImageView imgThumb;
        TextView tvVacancy;

        VH(@NonNull View itemView) {
            super(itemView);
            imgThumb = itemView.findViewById(R.id.imgThumb);
            tvVacancy = itemView.findViewById(R.id.tvVacancy);
        }
    }
}
