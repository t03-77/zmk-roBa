/*
 * 日本語配列（JIS）として設定された Windows で、刻印どおりの記号を出すための別名。
 * 普段のロジクール/エレコムの日本語キーボードと同じ PC 設定のまま使えるようにする。
 *
 * キーボードが送るのは「キーの位置」なので、US配列の名前のままだと
 * 日本語配列のPCでは別の記号になる（例: LBKT は JIS では @）。ここで読み替える。
 */
#pragma once

#define JP_MINUS  MINUS        /* -   Shift で = */
#define JP_EQUAL  LS(MINUS)    /* =  */
#define JP_CARET  EQUAL        /* ^   Shift で ~ */
#define JP_TILDE  LS(EQUAL)    /* ~  */
#define JP_YEN    INT3         /* ¥（\） Shift で | */
#define JP_PIPE   LS(INT3)     /* |  */
#define JP_AT     LBKT         /* @   Shift で ` */
#define JP_GRAVE  LS(LBKT)     /* `  */
#define JP_LBKT   RBKT         /* [   Shift で { */
#define JP_LBRC   LS(RBKT)     /* {  */
#define JP_RBKT   NUHS         /* ]   Shift で } */
#define JP_RBRC   LS(NUHS)     /* }  */
#define JP_SEMI   SEMI         /* ;   Shift で + */
#define JP_PLUS   LS(SEMI)     /* +  */
#define JP_COLON  SQT          /* :   Shift で * */
#define JP_STAR   LS(SQT)      /* *  */
#define JP_BSLH   INT1         /* \（ろ） Shift で _ */
#define JP_UNDER  LS(INT1)     /* _  */
#define JP_EXCL   LS(N1)       /* !  */
#define JP_DQT    LS(N2)       /* "  */
#define JP_HASH   LS(N3)       /* #  */
#define JP_DLLR   LS(N4)       /* $  */
#define JP_PRCNT  LS(N5)       /* %  */
#define JP_AMPS   LS(N6)       /* &  */
#define JP_SQT    LS(N7)       /* '  */
#define JP_LPAR   LS(N8)       /* (  */
#define JP_RPAR   LS(N9)       /* )  */
#define JP_LT     LS(COMMA)    /* <  */
#define JP_GT     LS(DOT)      /* >  */
#define JP_QMARK  LS(FSLH)     /* ?  */

/* Microsoft IME は LANG2 で IME オフ、LANG1 で IME オン（設定変更不要） */
#define JP_EISU   LANG2
#define JP_KANA   LANG1
