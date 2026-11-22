package com.uece.nutriia.ui.resultado

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.Toast
import com.google.android.material.bottomsheet.BottomSheetDialogFragment
import com.uece.nutriia.R
import com.uece.nutriia.databinding.BottomSheetAvaliacaoBinding

class AvaliacaoBottomSheet : BottomSheetDialogFragment() {

    private var _binding: BottomSheetAvaliacaoBinding? = null
    private val binding get() = _binding!!

    private var nota = 0
    private lateinit var estrelas: List<ImageView>

    override fun getTheme() = R.style.ThemeOverlay_NutriIA_BottomSheet

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?
    ): View {
        _binding = BottomSheetAvaliacaoBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        val produto = arguments?.getString(ARG_PRODUTO).orEmpty()
        val marca = arguments?.getString(ARG_MARCA)
        binding.txtProdutoAvaliacao.text = listOfNotNull(
            produto.takeIf { it.isNotBlank() },
            marca?.takeIf { it.isNotBlank() }
        ).joinToString(" · ")

        estrelas = listOf(binding.star1, binding.star2, binding.star3, binding.star4, binding.star5)
        estrelas.forEachIndexed { index, star ->
            star.setOnClickListener { definirNota(index + 1) }
        }

        binding.btnAgoraNao.setOnClickListener { dismiss() }
        binding.btnEnviar.setOnClickListener { enviar() }
    }

    private fun definirNota(valor: Int) {
        nota = valor
        estrelas.forEachIndexed { index, star ->
            star.setImageResource(
                if (index < valor) R.drawable.ic_star_filled else R.drawable.ic_star_outline
            )
        }
        binding.txtNotaLabel.text = when (valor) {
            1 -> "Muito ruim"
            2 -> "Ruim"
            3 -> "Regular"
            4 -> "Bom"
            else -> "Excelente"
        }
    }

    private fun enviar() {
        if (nota == 0) {
            binding.txtNotaLabel.text = getString(R.string.rate_choose_stars)
            return
        }
        val recomenda: Boolean? = when (binding.grupoRecomenda.checkedButtonId) {
            R.id.btnSim -> true
            R.id.btnNao -> false
            else -> null
        }

        // TODO (depois): enviar nota e recomenda para a rota do backend
        Toast.makeText(requireContext(), R.string.rate_thanks, Toast.LENGTH_SHORT).show()
        dismiss()
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    companion object {
        private const val ARG_PRODUTO = "produto"
        private const val ARG_MARCA = "marca"

        fun newInstance(produto: String, marca: String?) = AvaliacaoBottomSheet().apply {
            arguments = Bundle().apply {
                putString(ARG_PRODUTO, produto)
                putString(ARG_MARCA, marca)
            }
        }
    }
}