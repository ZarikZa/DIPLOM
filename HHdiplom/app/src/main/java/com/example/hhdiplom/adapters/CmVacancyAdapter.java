package com.example.hhdiplom.adapters;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.models.Vacancy;

import java.util.List;

public class CmVacancyAdapter extends RecyclerView.Adapter<CmVacancyAdapter.VH> {

    public interface OnVacancyActionListener {
        void onUploadVideoClicked(Vacancy vacancy);
    }

    private List<Vacancy> items;
    private final OnVacancyActionListener listener;

    public CmVacancyAdapter(List<Vacancy> items, OnVacancyActionListener listener) {
        this.items = items;
        this.listener = listener;
    }

    public void setItems(List<Vacancy> newItems) {
        this.items = newItems;
        notifyDataSetChanged();
    }

    @NonNull
    @Override
    public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_cm_vacancy, parent, false);
        return new VH(v);
    }

    @Override
    public void onBindViewHolder(@NonNull VH holder, int position) {
        Vacancy v = items.get(position);
        holder.tvTitle.setText(v.getPosition());
        holder.tvMeta.setText(v.getCity() + " • " + v.getCategory());
        holder.btnUpload.setOnClickListener(click -> listener.onUploadVideoClicked(v));
    }

    @Override
    public int getItemCount() {
        return items == null ? 0 : items.size();
    }

    static class VH extends RecyclerView.ViewHolder {
        TextView tvTitle;
        TextView tvMeta;
        Button btnUpload;

        VH(@NonNull View itemView) {
            super(itemView);
            tvTitle = itemView.findViewById(R.id.tvCMVacancyTitle);
            tvMeta = itemView.findViewById(R.id.tvCMVacancyMeta);
            btnUpload = itemView.findViewById(R.id.btnCMUpload);
        }
    }
}
