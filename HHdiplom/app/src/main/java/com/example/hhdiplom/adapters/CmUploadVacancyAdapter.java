package com.example.hhdiplom.adapters;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.models.Vacancy;
import com.google.android.material.button.MaterialButton;

import java.util.List;

public class CmUploadVacancyAdapter extends RecyclerView.Adapter<CmUploadVacancyAdapter.VH> {

    public interface OnVacancyPickListener {
        void onPickVacancy(Vacancy vacancy);
    }

    private final List<Vacancy> items;
    private final OnVacancyPickListener listener;

    public CmUploadVacancyAdapter(List<Vacancy> items, OnVacancyPickListener listener) {
        this.items = items;
        this.listener = listener;
    }

    @NonNull
    @Override
    public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_cm_upload_vacancy, parent, false);
        return new VH(v);
    }

    @Override
    public void onBindViewHolder(@NonNull VH h, int position) {
        Vacancy v = items.get(position);

        h.title.setText(v.getPosition());
        h.meta.setText(v.getCity() + " • " + v.getCompanyName());

        h.btnPick.setOnClickListener(view -> {
            if (listener != null) listener.onPickVacancy(v);
        });

        // Можно сделать “тап по карточке” тоже выбирающим
        h.itemView.setOnClickListener(view -> {
            if (listener != null) listener.onPickVacancy(v);
        });
    }

    @Override
    public int getItemCount() {
        return items == null ? 0 : items.size();
    }

    static class VH extends RecyclerView.ViewHolder {
        TextView title;
        TextView meta;
        MaterialButton btnPick;

        VH(@NonNull View itemView) {
            super(itemView);
            title = itemView.findViewById(R.id.title);
            meta = itemView.findViewById(R.id.meta);
            btnPick = itemView.findViewById(R.id.btnPick);
        }
    }
}
