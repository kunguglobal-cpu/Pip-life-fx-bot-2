package com.piplifefx.bot;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Handler;
import android.widget.*;
import java.io.*;

public class MainActivity extends Activity {
    EditText token, account;
    Switch live;
    TextView status, log;
    Handler handler = new Handler();
    Runnable poll = new Runnable() {
        @Override public void run() {
            readLog();
            handler.postDelayed(this, 1000);
        }
    };

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(R.layout.activity_main);
        token=findViewById(R.id.token); account=findViewById(R.id.account);
        live=findViewById(R.id.live); status=findViewById(R.id.status); log=findViewById(R.id.log);
        live.setChecked(false);
        findViewById(R.id.start).setOnClickListener(v -> startBot());
        findViewById(R.id.stop).setOnClickListener(v -> stopBot());
        if (android.os.Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 10);
        }
        handler.post(poll);
    }

    void startBot() {
        String t=token.getText().toString().trim();
        String a=account.getText().toString().trim();
        if(t.isEmpty() || a.isEmpty()) {
            Toast.makeText(this,"Enter MetaAPI token and account ID",Toast.LENGTH_LONG).show();
            return;
        }
        Intent i=new Intent(this, BotService.class);
        i.putExtra("token",t); i.putExtra("account",a); i.putExtra("live",live.isChecked());
        if(android.os.Build.VERSION.SDK_INT>=26) startForegroundService(i); else startService(i);
        status.setText(live.isChecked() ? "Status: LIVE MODE STARTED" : "Status: DRY RUN STARTED");
    }

    void stopBot() {
        stopService(new Intent(this, BotService.class));
        status.setText("Status: STOPPED");
    }

    void readLog() {
        try {
            File f=new File(getFilesDir(),"piplife_bot/bot.log");
            if(!f.exists()) return;
            BufferedReader r=new BufferedReader(new FileReader(f));
            StringBuilder s=new StringBuilder(); String line; int n=0;
            while((line=r.readLine())!=null && n++<120) s.append(line).append("\n");
            r.close(); log.setText(s.toString());
        } catch(Exception ignored) {}
    }

    @Override protected void onDestroy() {
        handler.removeCallbacks(poll);
        super.onDestroy();
    }
}
