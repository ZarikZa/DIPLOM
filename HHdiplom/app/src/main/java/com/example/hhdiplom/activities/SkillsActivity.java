package com.example.hhdiplom.activities;

import android.text.TextUtils;
import android.os.Bundle;
import android.widget.EditText;
import android.widget.Button;
import android.widget.ImageButton;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.adapters.SkillsSelectAdapter;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.ApplicantSkill;
import com.example.hhdiplom.models.ApplicantSkillItem;
import com.example.hhdiplom.models.ApplicantSkillSuggestionCreateRequest;
import com.example.hhdiplom.models.ApplicantSkillSuggestionResponse;
import com.example.hhdiplom.models.SkillItem;
import com.example.hhdiplom.models.SkillsResponse;
import com.example.hhdiplom.models.SkillsUpsertRequest;
import com.example.hhdiplom.utils.ProfanityValidator;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class SkillsActivity extends AppCompatActivity {

    private RecyclerView rvSkills;
    private Button btnSaveSkills;
    private Button btnSuggestSkill;

    private ApiService apiService;
    private SkillsSelectAdapter adapter;
    private final List<SkillsSelectAdapter.SkillRow> rows = new ArrayList<>();
    private final Map<Integer, Integer> myLevels = new HashMap<>();
    private final Map<String, String> mySuggestionStatuses = new HashMap<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_skills);

        apiService = ApiClient.getApiService();

        rvSkills = findViewById(R.id.rvSkills);
        btnSaveSkills = findViewById(R.id.btnSaveSkills);
        btnSuggestSkill = findViewById(R.id.btnSuggestSkill);
        ImageButton btnBack = findViewById(R.id.btnBack);

        adapter = new SkillsSelectAdapter(rows);
        rvSkills.setLayoutManager(new LinearLayoutManager(this));
        rvSkills.setAdapter(adapter);

        btnBack.setOnClickListener(v -> finish());
        btnSaveSkills.setOnClickListener(v -> saveSkills());
        btnSuggestSkill.setOnClickListener(v -> openSuggestSkillDialog());

        loadMySkillsThenAllSkills();
        loadMySkillSuggestions();
    }

    private void loadMySkillsThenAllSkills() {
        apiService.getMySkills().enqueue(new Callback<List<ApplicantSkill>>() {
            @Override
            public void onResponse(Call<List<ApplicantSkill>> call, Response<List<ApplicantSkill>> response) {
                myLevels.clear();
                if (response.isSuccessful() && response.body() != null) {
                    for (ApplicantSkill it : response.body()) {
                        myLevels.put(it.skill, it.level);
                    }
                }
                loadAllSkills();
            }

            @Override
            public void onFailure(Call<List<ApplicantSkill>> call, Throwable t) {
                myLevels.clear();
                loadAllSkills();
            }
        });
    }

    private void loadAllSkills() {
        apiService.getSkills().enqueue(new Callback<SkillsResponse>() {
            @Override
            public void onResponse(Call<SkillsResponse> call, Response<SkillsResponse> response) {
                if (!response.isSuccessful() || response.body() == null || response.body().getResults() == null) {
                    Toast.makeText(SkillsActivity.this, getString(R.string.skills_load_failed), Toast.LENGTH_SHORT).show();
                    return;
                }

                rows.clear();
                for (SkillItem s : response.body().getResults()) {
                    SkillsSelectAdapter.SkillRow r = new SkillsSelectAdapter.SkillRow();
                    r.skill = s;
                    if (myLevels.containsKey(s.id)) {
                        r.selected = true;
                        r.level = myLevels.get(s.id);
                    } else {
                        r.selected = false;
                        r.level = 1;
                    }
                    rows.add(r);
                }
                adapter.notifyDataSetChanged();
            }

            @Override
            public void onFailure(Call<SkillsResponse> call, Throwable t) {
                Toast.makeText(SkillsActivity.this, getString(R.string.error_network_with_message, t.getMessage()), Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void saveSkills() {
        List<SkillsUpsertRequest.SkillLevel> payload = new ArrayList<>();
        for (SkillsSelectAdapter.SkillRow r : adapter.getRows()) {
            if (r.selected) {
                payload.add(new SkillsUpsertRequest.SkillLevel(r.skill.id, r.level));
            }
        }

        if (payload.size() > 5) {
            Toast.makeText(this, getString(R.string.skills_limit_error), Toast.LENGTH_SHORT).show();
            return;
        }

        SkillsUpsertRequest body = new SkillsUpsertRequest(payload);
        apiService.saveMySkills(body).enqueue(new Callback<List<ApplicantSkillItem>>() {
            @Override
            public void onResponse(Call<List<ApplicantSkillItem>> call, Response<List<ApplicantSkillItem>> response) {
                if (response.isSuccessful()) {
                    Toast.makeText(SkillsActivity.this, getString(R.string.skills_saved), Toast.LENGTH_SHORT).show();
                    finish();
                } else {
                    Toast.makeText(SkillsActivity.this, getString(R.string.skills_save_failed_code, response.code()), Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onFailure(Call<List<ApplicantSkillItem>> call, Throwable t) {
                Toast.makeText(SkillsActivity.this, getString(R.string.error_network_with_message, t.getMessage()), Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void openSuggestSkillDialog() {
        EditText input = new EditText(this);
        input.setHint(R.string.skills_suggestion_hint);
        input.setMaxLines(1);

        new AlertDialog.Builder(this)
                .setTitle(R.string.skills_suggestion_title)
                .setView(input)
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(R.string.send, (dialog, which) -> {
                    String raw = input.getText() == null ? "" : input.getText().toString();
                    String normalizedSkillName = normalizeSkillName(raw);
                    if (TextUtils.isEmpty(normalizedSkillName)) {
                        Toast.makeText(this, getString(R.string.skills_suggestion_empty), Toast.LENGTH_SHORT).show();
                        return;
                    }
                    if (isExistingSkill(normalizedSkillName)) {
                        Toast.makeText(this, "Такой навык уже есть в списке доступных.", Toast.LENGTH_SHORT).show();
                        return;
                    }

                    String existingStatus = mySuggestionStatuses.get(
                            normalizedSkillName.toLowerCase(Locale.ROOT)
                    );
                    if ("pending".equalsIgnoreCase(existingStatus)) {
                        Toast.makeText(this, "Такой навык уже отправлен на проверку администратору.", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    if ("approved".equalsIgnoreCase(existingStatus)) {
                        Toast.makeText(this, "Этот навык уже подтвержден администратором.", Toast.LENGTH_SHORT).show();
                        return;
                    }

                    if (ProfanityValidator.containsProfanity(normalizedSkillName)) {
                        Toast.makeText(this, ProfanityValidator.DEFAULT_ERROR_MESSAGE, Toast.LENGTH_SHORT).show();
                        return;
                    }
                    sendSkillSuggestion(normalizedSkillName);
                })
                .show();
    }

    private void loadMySkillSuggestions() {
        apiService.getMySkillSuggestions().enqueue(new Callback<List<ApplicantSkillSuggestionResponse>>() {
            @Override
            public void onResponse(Call<List<ApplicantSkillSuggestionResponse>> call, Response<List<ApplicantSkillSuggestionResponse>> response) {
                mySuggestionStatuses.clear();
                if (!response.isSuccessful() || response.body() == null) {
                    return;
                }

                for (ApplicantSkillSuggestionResponse suggestion : response.body()) {
                    String name = normalizeSkillName(suggestion.getName());
                    if (TextUtils.isEmpty(name)) {
                        continue;
                    }
                    String status = suggestion.getStatus() == null ? "" : suggestion.getStatus().trim();
                    mySuggestionStatuses.put(name.toLowerCase(Locale.ROOT), status);
                }
            }

            @Override
            public void onFailure(Call<List<ApplicantSkillSuggestionResponse>> call, Throwable t) {
                mySuggestionStatuses.clear();
            }
        });
    }

    private void sendSkillSuggestion(String skillName) {
        apiService.createSkillSuggestion(new ApplicantSkillSuggestionCreateRequest(skillName))
                .enqueue(new Callback<ApplicantSkillSuggestionResponse>() {
                    @Override
                    public void onResponse(Call<ApplicantSkillSuggestionResponse> call, Response<ApplicantSkillSuggestionResponse> response) {
                        if (response.isSuccessful()) {
                            String status = "pending";
                            if (response.body() != null && !TextUtils.isEmpty(response.body().getStatus())) {
                                status = response.body().getStatus().trim();
                            }
                            mySuggestionStatuses.put(skillName.toLowerCase(Locale.ROOT), status);

                            Toast.makeText(
                                    SkillsActivity.this,
                                    getString(R.string.skills_suggestion_sent),
                                    Toast.LENGTH_SHORT
                            ).show();
                        } else {
                            String serverError = extractServerErrorMessage(response);
                            if (!TextUtils.isEmpty(serverError)) {
                                Toast.makeText(
                                        SkillsActivity.this,
                                        serverError,
                                        Toast.LENGTH_LONG
                                ).show();
                                return;
                            }

                            Toast.makeText(
                                    SkillsActivity.this,
                                    getString(R.string.skills_suggestion_send_failed_code, response.code()),
                                    Toast.LENGTH_SHORT
                            ).show();
                        }
                    }

                    @Override
                    public void onFailure(Call<ApplicantSkillSuggestionResponse> call, Throwable t) {
                        Toast.makeText(
                                SkillsActivity.this,
                                getString(R.string.error_network_with_message, t.getMessage()),
                                Toast.LENGTH_SHORT
                        ).show();
                    }
                });
    }

    private String normalizeSkillName(String rawValue) {
        if (rawValue == null) {
            return "";
        }
        return rawValue.trim().replaceAll("\\s+", " ");
    }

    private boolean isExistingSkill(String skillName) {
        String normalizedCandidate = normalizeSkillName(skillName).toLowerCase(Locale.ROOT);
        if (TextUtils.isEmpty(normalizedCandidate)) {
            return false;
        }

        for (SkillsSelectAdapter.SkillRow row : rows) {
            if (row == null || row.skill == null) {
                continue;
            }
            String existingName = normalizeSkillName(row.skill.name).toLowerCase(Locale.ROOT);
            if (normalizedCandidate.equals(existingName)) {
                return true;
            }
        }
        return false;
    }

    private String extractServerErrorMessage(Response<?> response) {
        if (response == null || response.errorBody() == null) {
            return null;
        }
        try {
            String raw = response.errorBody().string();
            if (TextUtils.isEmpty(raw)) {
                return null;
            }

            JSONObject root = new JSONObject(raw);
            String detail = root.optString("detail", "").trim();
            if (!TextUtils.isEmpty(detail)) {
                return detail;
            }

            String nameError = extractFirstErrorItem(root.opt("name"));
            if (!TextUtils.isEmpty(nameError)) {
                return nameError;
            }

            Iterator<String> keys = root.keys();
            while (keys.hasNext()) {
                String key = keys.next();
                String value = extractFirstErrorItem(root.opt(key));
                if (!TextUtils.isEmpty(value)) {
                    return value;
                }
            }
        } catch (Exception ignored) {
        }
        return null;
    }

    private String extractFirstErrorItem(Object value) {
        if (value == null || value == JSONObject.NULL) {
            return null;
        }
        if (value instanceof JSONArray) {
            JSONArray array = (JSONArray) value;
            for (int i = 0; i < array.length(); i++) {
                String item = array.optString(i, "").trim();
                if (!TextUtils.isEmpty(item)) {
                    return item;
                }
            }
            return null;
        }
        String text = String.valueOf(value).trim();
        return TextUtils.isEmpty(text) ? null : text;
    }
}
