import { Product } from '../types';
import { GetServerSideProps } from 'next';
import Head from 'next/head';

import Home from '../components/Home';
import pool from '../lib/db';

interface Props {
  products: Product[];
}

export const getServerSideProps: GetServerSideProps<Props> = async () => {
  const results = await pool.query<Product>('SELECT * FROM public.product;');
  return { props: { products: results.rows } };
};

const GTMContainerID = process.env.NEXT_PUBLIC_GOOGLE_TAG_MANAGER_CONTAINER

const IndexPage = ({
  products,
}: Props) => {
  return (
    <>
      <Head>
        <title>Cookie House</title>
        <meta name="description" content="Sample Project used within Fides (github.com/ethyca/fides)" />
        <link rel="icon" href="/favicon.ico" />
        <link rel="stylesheet" href="https://rsms.me/inter/inter.css"></link>
        {/* Google Tag Manager */}
        {GTMContainerID ? <script
          dangerouslySetInnerHTML={{
            __html: `(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
            new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
            j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
            'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
            })(window,document,'script','dataLayer','${GTMContainerID}');`,
          }}
        /> : ""}
      </Head>

      {GTMContainerID ? <noscript
        dangerouslySetInnerHTML={{
          __html: `<iframe src="https://www.googletagmanager.com/ns.html?id=${GTMContainerID}"
          height="0" width="0" style="display:none;visibility:hidden"></iframe>`,
        }}
      /> : ""}

      <Home products={products} />
    </>
  );
};

export default IndexPage;